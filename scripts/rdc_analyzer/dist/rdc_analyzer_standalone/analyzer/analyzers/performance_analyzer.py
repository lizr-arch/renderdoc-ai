"""
性能分析器 (C.2)
================

分析帧的性能问题，检测:
- PERF001: 过度绘制
- PERF002: 状态冗余
- PERF003: 小批次绘制
- PERF004: 大纹理
- PERF005: 未压缩纹理
- PERF006: Alpha 混合过度使用
- PERF007: 频繁绑定
"""

from typing import List, Dict, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
import hashlib

from .base import BaseAnalyzer
from ..core.context import AnalysisContext
from ..core.types import (
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
    import json
    state_str = json.dumps(state_dict, sort_keys=True, default=str)
    return hashlib.md5(state_str.encode()).hexdigest()[:8]


# ============================================================================
# 性能分析器
# ============================================================================

class PerformanceAnalyzer(BaseAnalyzer):
    """
    性能分析器
    
    检测常见的性能问题，生成性能报告。
    """
    
    name = "performance"
    description = "Performance analyzer - detects common performance issues"
    dependencies = ["state", "resource"]
    
    def __init__(self, context: AnalysisContext):
        super().__init__(context)
        self.report = PerformanceReport()
        self._rules = self._load_rules()
        
        # 追踪状态
        self._prev_state: Dict[str, Any] = {}
        self._state_history: List[Tuple[int, str, str]] = []  # (event_id, state_type, hash)
        self._texture_bind_counts: Dict[str, int] = {}
        self._texture_events: Dict[str, List[int]] = {}
        self._shader_bind_counts: Dict[str, int] = {}
        self._blend_draw_count: int = 0
    
    def _load_rules(self) -> Dict[str, PerformanceRule]:
        """加载性能规则"""
        # 使用预定义规则，但可被上下文配置覆盖
        rules = dict(PERFORMANCE_RULES)
        
        # 从上下文获取自定义阈值
        for rule_id, rule in rules.items():
            for key in rule.thresholds:
                custom = self.context.get_threshold(f"{rule_id}_{key}", None)
                if custom is not None:
                    rule.thresholds[key] = custom
        
        return rules
    
    def analyze(self) -> None:
        """执行性能分析"""
        # 收集基础统计
        self._collect_statistics()
        
        # 运行各规则检测
        if self._rules.get("PERF001", PerformanceRule("", "", "", "", "")).enabled:
            self._check_overdraw()
        
        if self._rules.get("PERF002", PerformanceRule("", "", "", "", "")).enabled:
            self._check_state_redundancy()
        
        if self._rules.get("PERF003", PerformanceRule("", "", "", "", "")).enabled:
            self._check_small_batches()
        
        if self._rules.get("PERF004", PerformanceRule("", "", "", "", "")).enabled:
            self._check_large_textures()
        
        if self._rules.get("PERF005", PerformanceRule("", "", "", "", "")).enabled:
            self._check_uncompressed_textures()
        
        if self._rules.get("PERF006", PerformanceRule("", "", "", "", "")).enabled:
            self._check_alpha_blend_usage()
        
        if self._rules.get("PERF007", PerformanceRule("", "", "", "", "")).enabled:
            self._check_frequent_binding()
        
        # 汇总问题统计
        self._finalize_report()
        
        # 保存到上下文
        self.context.performance_report = self.report
    
    def _collect_statistics(self) -> None:
        """收集帧级统计数据"""
        draws = self.context.result.draws if hasattr(self.context.result, 'draws') else []
        dispatches = self.context.result.dispatches if hasattr(self.context.result, 'dispatches') else []
        textures = self.context.result.textures if hasattr(self.context.result, 'textures') else []
        buffers = self.context.result.buffers if hasattr(self.context.result, 'buffers') else []
        shaders = self.context.result.shaders if hasattr(self.context.result, 'shaders') else []
        
        self.report.total_draw_calls = len(draws)
        self.report.total_dispatches = len(dispatches)
        
        # 几何统计
        total_verts = 0
        total_tris = 0
        total_instances = 0
        
        prev_vs = None
        prev_ps = None
        prev_rt = None
        prev_blend = None
        prev_depth = None
        
        for draw in draws:
            # 统计几何
            if isinstance(draw, dict):
                vc = draw.get('vertex_count', 0) or draw.get('vertexCount', 0) or 0
                ic = draw.get('index_count', 0) or draw.get('indexCount', 0) or 0
                inst = draw.get('instance_count', 1) or draw.get('instanceCount', 1) or 1
                event_id = draw.get('event_id', 0) or draw.get('eventId', 0) or 0
                vs_id = draw.get('vs_id', '') or draw.get('vsId', '') or ''
                ps_id = draw.get('ps_id', '') or draw.get('psId', '') or ''
                rt_ids = draw.get('rt_ids', []) or draw.get('rtIds', []) or []
                blend_enabled = draw.get('blend_enabled', False) or draw.get('blendEnabled', False)
                depth_write = draw.get('depth_write', True)
            elif isinstance(draw, DrawCallInfo):
                vc = draw.vertex_count
                ic = draw.index_count
                inst = draw.instance_count
                event_id = draw.event_id
                vs_id = draw.vs_id
                ps_id = draw.ps_id
                rt_ids = draw.rt_ids
                blend_enabled = draw.blend_enabled
                depth_write = draw.depth_write
            else:
                continue
            
            effective_verts = vc if vc > 0 else ic
            total_verts += effective_verts * inst
            total_tris += (effective_verts // 3) * inst
            total_instances += inst
            
            # 状态变更统计
            if vs_id != prev_vs or ps_id != prev_ps:
                self.report.total_shader_changes += 1
                prev_vs = vs_id
                prev_ps = ps_id
            
            rt_key = str(sorted(rt_ids))
            if rt_key != prev_rt:
                self.report.total_rt_changes += 1
                prev_rt = rt_key
            
            if blend_enabled != prev_blend:
                self.report.total_blend_changes += 1
                prev_blend = blend_enabled
            
            if depth_write != prev_depth:
                self.report.total_depth_changes += 1
                prev_depth = depth_write
            
            # 追踪 blend 使用
            if blend_enabled:
                self._blend_draw_count += 1
            
            # 构建性能指标
            metrics = PerformanceMetrics(
                event_id=event_id,
                vertex_count=vc,
                triangle_count=effective_verts // 3,
                instance_count=inst,
                alpha_blend_enabled=blend_enabled,
            )
            self.report.metrics_by_event[event_id] = metrics
        
        self.report.total_vertices = total_verts
        self.report.total_triangles = total_tris
        self.report.total_instances = total_instances
        
        # 资源统计
        self.report.unique_textures = len(textures)
        self.report.unique_buffers = len(buffers)
        self.report.unique_shaders = len(shaders)
        
        # 内存统计
        total_tex_mem = 0
        for tex in textures:
            if isinstance(tex, dict):
                total_tex_mem += tex.get('memory_size', 0) or tex.get('memorySize', 0) or 0
            elif isinstance(tex, TextureInfo):
                total_tex_mem += tex.memory_size
        self.report.total_texture_memory_mb = total_tex_mem / (1024 * 1024)
        
        total_buf_mem = 0
        for buf in buffers:
            if isinstance(buf, dict):
                total_buf_mem += buf.get('size', 0)
            else:
                total_buf_mem += getattr(buf, 'size', 0)
        self.report.total_buffer_memory_mb = total_buf_mem / (1024 * 1024)
    
    # ========================================================================
    # PERF001: 过度绘制检测
    # ========================================================================
    
    def _check_overdraw(self) -> None:
        """
        检测过度绘制
        
        基于启发式规则: 如果同一 RenderTarget 被多个 Draw 绘制，可能存在过度绘制。
        精确的过度绘制需要像素级分析，这里使用粗略估计。
        """
        rule = self._rules.get("PERF001")
        if not rule:
            return
        
        max_overdraw = rule.thresholds.get("max_overdraw", 4)
        
        # 按 RenderTarget 统计 Draw 次数
        rt_draw_counts: Dict[str, List[int]] = {}
        
        draws = self.context.result.draws if hasattr(self.context.result, 'draws') else []
        for draw in draws:
            if isinstance(draw, dict):
                rt_ids = draw.get('rt_ids', []) or draw.get('rtIds', []) or []
                event_id = draw.get('event_id', 0) or draw.get('eventId', 0)
            elif isinstance(draw, DrawCallInfo):
                rt_ids = draw.rt_ids
                event_id = draw.event_id
            else:
                continue
            
            for rt_id in rt_ids:
                if rt_id not in rt_draw_counts:
                    rt_draw_counts[rt_id] = []
                rt_draw_counts[rt_id].append(event_id)
        
        # 检查是否超过阈值
        for rt_id, events in rt_draw_counts.items():
            if len(events) > max_overdraw:
                issue = PerformanceIssue(
                    rule_id="PERF001",
                    severity=rule.severity,
                    category=rule.category,
                    title=rule.name,
                    message=f"RenderTarget {rt_id} 被绘制 {len(events)} 次，可能存在过度绘制",
                    resource_id=rt_id,
                    actual_value=len(events),
                    threshold_value=max_overdraw,
                    impact_score=min(100, (len(events) / max_overdraw) * 25),
                    suggestion="考虑合并绘制调用或优化渲染顺序",
                    related_events=events[:20],  # 限制列表大小
                )
                self.report.issues.append(issue)
    
    # ========================================================================
    # PERF002: 状态冗余检测
    # ========================================================================
    
    def _check_state_redundancy(self) -> None:
        """检测连续相同状态设置"""
        rule = self._rules.get("PERF002")
        if not rule:
            return
        
        min_redundant = rule.thresholds.get("min_redundant_count", 3)
        
        # 追踪状态变化
        draws = self.context.result.draws if hasattr(self.context.result, 'draws') else []
        
        prev_shader_state = None
        prev_blend_state = None
        shader_redundant_count = 0
        blend_redundant_count = 0
        shader_redundant_start = 0
        blend_redundant_start = 0
        
        redundant_issues: List[PerformanceIssue] = []
        
        for i, draw in enumerate(draws):
            if isinstance(draw, dict):
                event_id = draw.get('event_id', 0) or draw.get('eventId', i)
                vs_id = draw.get('vs_id', '') or draw.get('vsId', '')
                ps_id = draw.get('ps_id', '') or draw.get('psId', '')
                blend_enabled = draw.get('blend_enabled', False)
            elif isinstance(draw, DrawCallInfo):
                event_id = draw.event_id
                vs_id = draw.vs_id
                ps_id = draw.ps_id
                blend_enabled = draw.blend_enabled
            else:
                continue
            
            # Shader 状态
            shader_state = f"{vs_id}|{ps_id}"
            if shader_state == prev_shader_state:
                shader_redundant_count += 1
            else:
                if shader_redundant_count >= min_redundant:
                    redundant_issues.append(self._create_redundancy_issue(
                        "shader", shader_redundant_count, shader_redundant_start, event_id - 1
                    ))
                shader_redundant_count = 1
                shader_redundant_start = event_id
            prev_shader_state = shader_state
            
            # Blend 状态
            blend_state = str(blend_enabled)
            if blend_state == prev_blend_state:
                blend_redundant_count += 1
            else:
                if blend_redundant_count >= min_redundant:
                    redundant_issues.append(self._create_redundancy_issue(
                        "blend", blend_redundant_count, blend_redundant_start, event_id - 1
                    ))
                blend_redundant_count = 1
                blend_redundant_start = event_id
            prev_blend_state = blend_state
        
        # 检查末尾
        if shader_redundant_count >= min_redundant:
            redundant_issues.append(self._create_redundancy_issue(
                "shader", shader_redundant_count, shader_redundant_start, draws[-1].event_id if draws else 0
            ))
        
        self.report.issues.extend(redundant_issues)
        self.report.redundant_state_sets = len(redundant_issues)
    
    def _create_redundancy_issue(
        self, state_type: str, count: int, start_eid: int, end_eid: int
    ) -> PerformanceIssue:
        """创建状态冗余问题"""
        rule = self._rules["PERF002"]
        return PerformanceIssue(
            rule_id="PERF002",
            severity=rule.severity,
            category=rule.category,
            title=f"{rule.name} ({state_type})",
            message=f"连续 {count} 次 Draw 使用相同的 {state_type} 状态",
            event_range=(start_eid, end_eid),
            actual_value=count,
            threshold_value=rule.thresholds.get("min_redundant_count", 3),
            impact_score=min(50, count * 2),
            suggestion=f"考虑按 {state_type} 状态批量排序绘制调用",
        )
    
    # ========================================================================
    # PERF003: 小批次绘制检测
    # ========================================================================
    
    def _check_small_batches(self) -> None:
        """检测顶点数过少的绘制调用"""
        rule = self._rules.get("PERF003")
        if not rule:
            return
        
        min_vertices = rule.thresholds.get("min_vertices", 100)
        min_triangles = rule.thresholds.get("min_triangles", 30)
        
        small_batch_events: List[int] = []
        
        draws = self.context.result.draws if hasattr(self.context.result, 'draws') else []
        for draw in draws:
            if isinstance(draw, dict):
                event_id = draw.get('event_id', 0) or draw.get('eventId', 0)
                vc = draw.get('vertex_count', 0) or draw.get('vertexCount', 0) or 0
                ic = draw.get('index_count', 0) or draw.get('indexCount', 0) or 0
            elif isinstance(draw, DrawCallInfo):
                event_id = draw.event_id
                vc = draw.vertex_count
                ic = draw.index_count
            else:
                continue
            
            effective_verts = vc if vc > 0 else ic
            tris = effective_verts // 3
            
            if effective_verts > 0 and (effective_verts < min_vertices or tris < min_triangles):
                small_batch_events.append(event_id)
        
        if len(small_batch_events) > 5:  # 只有大量小批次才报告
            issue = PerformanceIssue(
                rule_id="PERF003",
                severity=rule.severity,
                category=rule.category,
                title=rule.name,
                message=f"检测到 {len(small_batch_events)} 个小批次绘制调用 (< {min_vertices} 顶点)",
                actual_value=len(small_batch_events),
                threshold_value=5,
                impact_score=min(100, len(small_batch_events) * 2),
                suggestion="考虑使用实例化渲染或合并小批次绘制",
                related_events=small_batch_events[:30],
            )
            self.report.issues.append(issue)
    
    # ========================================================================
    # PERF004: 大纹理检测
    # ========================================================================
    
    def _check_large_textures(self) -> None:
        """检测超大纹理"""
        rule = self._rules.get("PERF004")
        if not rule:
            return
        
        max_dimension = rule.thresholds.get("max_dimension", 4096)
        max_memory_mb = rule.thresholds.get("max_memory_mb", 64)
        
        textures = self.context.result.textures if hasattr(self.context.result, 'textures') else []
        
        for tex in textures:
            if isinstance(tex, dict):
                res_id = tex.get('resource_id', '') or tex.get('resourceId', '')
                name = tex.get('name', '')
                width = tex.get('width', 0)
                height = tex.get('height', 0)
                mem = tex.get('memory_size', 0) or tex.get('memorySize', 0)
            elif isinstance(tex, TextureInfo):
                res_id = tex.resource_id
                name = tex.name
                width = tex.width
                height = tex.height
                mem = tex.memory_size
            else:
                continue
            
            mem_mb = mem / (1024 * 1024)
            max_dim = max(width, height)
            
            if max_dim > max_dimension or mem_mb > max_memory_mb:
                issue = PerformanceIssue(
                    rule_id="PERF004",
                    severity=rule.severity,
                    category=rule.category,
                    title=rule.name,
                    message=f"纹理 {name or res_id} ({width}x{height}, {mem_mb:.1f}MB) 超过推荐尺寸",
                    resource_id=res_id,
                    actual_value=f"{width}x{height}, {mem_mb:.1f}MB",
                    threshold_value=f"{max_dimension}x{max_dimension}, {max_memory_mb}MB",
                    impact_score=min(100, (max_dim / max_dimension) * 30 + (mem_mb / max_memory_mb) * 30),
                    suggestion="考虑降低纹理分辨率或使用纹理流送",
                )
                self.report.issues.append(issue)
    
    # ========================================================================
    # PERF005: 未压缩纹理检测
    # ========================================================================
    
    def _check_uncompressed_textures(self) -> None:
        """检测未使用压缩格式的纹理"""
        rule = self._rules.get("PERF005")
        if not rule:
            return
        
        min_size = rule.thresholds.get("min_size_for_compression", 256)
        
        uncompressed: List[Tuple[str, str, int, int]] = []
        
        textures = self.context.result.textures if hasattr(self.context.result, 'textures') else []
        
        for tex in textures:
            if isinstance(tex, dict):
                res_id = tex.get('resource_id', '') or tex.get('resourceId', '')
                name = tex.get('name', '')
                width = tex.get('width', 0)
                height = tex.get('height', 0)
                fmt = tex.get('format', '')
                is_rt = tex.get('is_render_target', False) or tex.get('isRenderTarget', False)
                is_ds = tex.get('is_depth_stencil', False) or tex.get('isDepthStencil', False)
            elif isinstance(tex, TextureInfo):
                res_id = tex.resource_id
                name = tex.name
                width = tex.width
                height = tex.height
                fmt = tex.format
                is_rt = tex.is_render_target
                is_ds = tex.is_depth_stencil
            else:
                continue
            
            # 跳过 RenderTarget 和 DepthStencil (通常不压缩)
            if is_rt or is_ds:
                continue
            
            # 检查是否足够大需要压缩
            if width >= min_size and height >= min_size:
                if not is_compressed_format(fmt):
                    uncompressed.append((res_id, name, width, height))
        
        if uncompressed:
            issue = PerformanceIssue(
                rule_id="PERF005",
                severity=rule.severity,
                category=rule.category,
                title=rule.name,
                message=f"检测到 {len(uncompressed)} 个未压缩的大纹理",
                actual_value=len(uncompressed),
                threshold_value=0,
                impact_score=min(50, len(uncompressed) * 5),
                suggestion="考虑使用 BC/DXT 压缩格式减少内存占用和带宽",
            )
            self.report.issues.append(issue)
    
    # ========================================================================
    # PERF006: Alpha 混合过度使用检测
    # ========================================================================
    
    def _check_alpha_blend_usage(self) -> None:
        """检测 Alpha 混合过度使用"""
        rule = self._rules.get("PERF006")
        if not rule:
            return
        
        max_ratio = rule.thresholds.get("max_blend_ratio", 0.5)
        
        if self.report.total_draw_calls == 0:
            return
        
        blend_ratio = self._blend_draw_count / self.report.total_draw_calls
        
        if blend_ratio > max_ratio:
            issue = PerformanceIssue(
                rule_id="PERF006",
                severity=rule.severity,
                category=rule.category,
                title=rule.name,
                message=f"{self._blend_draw_count}/{self.report.total_draw_calls} ({blend_ratio*100:.0f}%) 的绘制调用使用 Alpha 混合",
                actual_value=f"{blend_ratio*100:.1f}%",
                threshold_value=f"{max_ratio*100:.0f}%",
                impact_score=min(80, (blend_ratio / max_ratio) * 40),
                suggestion="检查是否有不必要的透明绘制，考虑使用 Alpha Test 替代 Alpha Blend",
            )
            self.report.issues.append(issue)
    
    # ========================================================================
    # PERF007: 频繁绑定检测
    # ========================================================================
    
    def _check_frequent_binding(self) -> None:
        """检测资源频繁绑定/解绑"""
        rule = self._rules.get("PERF007")
        if not rule:
            return
        
        max_rebind = rule.thresholds.get("max_rebind_count", 10)
        
        # 统计每个纹理被绑定的次数
        texture_binds: Dict[str, int] = {}
        
        draws = self.context.result.draws if hasattr(self.context.result, 'draws') else []
        for draw in draws:
            if isinstance(draw, dict):
                # 假设 draw 中有绑定的纹理列表
                bound_textures = draw.get('bound_textures', []) or draw.get('boundTextures', [])
            else:
                bound_textures = getattr(draw, 'bound_textures', [])
            
            for tex_id in bound_textures:
                texture_binds[tex_id] = texture_binds.get(tex_id, 0) + 1
        
        # 检查超过阈值的绑定
        frequent_binds = [(tid, count) for tid, count in texture_binds.items() if count > max_rebind]
        
        if frequent_binds:
            issue = PerformanceIssue(
                rule_id="PERF007",
                severity=rule.severity,
                category=rule.category,
                title=rule.name,
                message=f"检测到 {len(frequent_binds)} 个纹理被频繁绑定 (> {max_rebind} 次)",
                actual_value=len(frequent_binds),
                threshold_value=max_rebind,
                impact_score=min(40, len(frequent_binds) * 5),
                suggestion="考虑使用纹理数组或按材质批量排序绘制调用",
            )
            self.report.issues.append(issue)
    
    # ========================================================================
    # 报告汇总
    # ========================================================================
    
    def _build_evidence_chains(self) -> None:
        """M2.1: 为每个 Issue 生成证据链"""
        try:
            from ..core.evidence_chain_builder import EvidenceChainBuilder
            
            # 尝试从上下文获取资源使用索引
            usage_index = getattr(self.context, 'resource_usage_index', None)
            builder = EvidenceChainBuilder(usage_index)
            
            for issue in self.report.issues:
                try:
                    issue.evidence_chain = builder.build(issue)
                except Exception as e:
                    # 单个 Issue 构建失败不影响整体
                    pass
        except ImportError:
            # 如果导入失败，跳过证据链生成
            pass
    
    def _finalize_report(self) -> None:
        """汇总并计算最终评分"""
        # M2.1: 为每个 Issue 生成证据链
        self._build_evidence_chains()
        
        # 按严重级别统计
        for issue in self.report.issues:
            if issue.severity == "critical":
                self.report.critical_count += 1
            elif issue.severity == "warning":
                self.report.warning_count += 1
            else:
                self.report.info_count += 1
            
            # 按类别统计
            if issue.category == "overdraw":
                self.report.overdraw_issues += 1
            elif issue.category == "state":
                self.report.state_issues += 1
            elif issue.category == "batch":
                self.report.batch_issues += 1
            elif issue.category == "texture":
                self.report.texture_issues += 1
            elif issue.category == "blend":
                self.report.blend_issues += 1
            elif issue.category == "binding":
                self.report.binding_issues += 1
        
        # 计算总体评分 (基于问题影响)
        total_impact = sum(issue.impact_score for issue in self.report.issues)
        # 评分 = 100 - 影响分 (限制在 0-100)
        self.report.overall_score = max(0, min(100, 100 - total_impact / 2))
        
        # 生成建议列表
        self._generate_recommendations()
    
    def _generate_recommendations(self) -> None:
        """生成优先级排序的建议列表，包含具体可操作信息"""
        recs = []
        
        # 按影响分排序问题
        sorted_issues = sorted(
            self.report.issues,
            key=lambda x: x.impact_score,
            reverse=True
        )
        
        for issue in sorted_issues[:5]:  # 取前 5 个最严重的问题
            rec = self._format_detailed_recommendation(issue)
            if rec:
                recs.append(rec)
        
        # 添加通用建议（带具体数据）
        if self.report.total_shader_changes > self.report.total_draw_calls * 0.5:
            change_rate = (self.report.total_shader_changes / max(1, self.report.total_draw_calls)) * 100
            recs.append({
                "priority": "medium",
                "rule": "PERF_SHADER",
                "title": "Shader 变更过于频繁",
                "detail": f"检测到 {self.report.total_shader_changes} 次 Shader 切换（{self.report.total_draw_calls} 次 Draw），变更率 {change_rate:.0f}%",
                "action": "按 Shader 对 Draw Call 进行批量排序，将使用相同 Shader 的绘制调用分组执行",
                "impact": f"预计减少 {int(self.report.total_shader_changes * 0.6)} 次状态切换",
            })
        
        if self.report.total_rt_changes > 10:
            recs.append({
                "priority": "medium",
                "rule": "PERF_RT",
                "title": "RenderTarget 频繁切换",
                "detail": f"检测到 {self.report.total_rt_changes} 次 RenderTarget 切换",
                "action": "优化渲染顺序，将同一 RenderTarget 的绘制调用分组执行，减少 SetRenderTarget 调用",
                "impact": f"预计减少 {int(self.report.total_rt_changes * 0.4)} 次 RT 切换开销",
            })
        
        # 添加内存相关建议
        if self.report.total_texture_memory_mb > 512:
            recs.append({
                "priority": "high" if self.report.total_texture_memory_mb > 1024 else "medium",
                "rule": "PERF_MEMORY",
                "title": "纹理内存占用过高",
                "detail": f"纹理总内存 {self.report.total_texture_memory_mb:.1f} MB，{self.report.unique_textures} 张纹理",
                "action": "检查是否有未使用的纹理、重复加载的纹理，或可降低分辨率的纹理",
                "impact": f"优化后预计可节省 {self.report.total_texture_memory_mb * 0.3:.0f} MB 内存",
            })
        
        self.report.recommendations = recs
    
    def _format_detailed_recommendation(self, issue: PerformanceIssue) -> Optional[dict]:
        """将 Issue 转换为详细的推荐信息"""
        if not issue:
            return None
        
        # 构建带具体数据的建议
        rec = {
            "priority": issue.severity,
            "rule": issue.rule_id,
            "title": issue.title,
            "detail": issue.message,
            "action": issue.suggestion or "请查看详细分析报告",
        }
        
        # 添加影响评估
        if issue.actual_value and issue.threshold_value:
            rec["threshold"] = f"阈值: {issue.threshold_value}, 实际: {issue.actual_value}"
        
        # 根据规则 ID 生成具体影响估算
        if issue.rule_id == "PERF001":  # 过度绘制
            events_count = len(issue.related_events) if issue.related_events else 0
            rec["impact"] = f"涉及 {events_count} 个 Draw Call，预计可减少 {events_count // 2} 次重复绘制"
        elif issue.rule_id == "PERF003":  # 小批次
            events_count = len(issue.related_events) if issue.related_events else 0
            rec["impact"] = f"合并后预计可减少 {events_count * 0.7:.0f} 次 Draw Call"
        elif issue.rule_id == "PERF004":  # 大纹理
            rec["impact"] = f"降低分辨率可显著减少显存占用和带宽消耗"
        elif issue.rule_id == "PERF005":  # 未压缩纹理
            rec["impact"] = f"使用 BC7 压缩可减少 75% 内存占用"
        elif issue.rule_id == "PERF006":  # Alpha 混合
            rec["impact"] = "减少不必要的透明绘制可提升 GPU 填充率"
        elif issue.rule_id == "PERF007":  # 频繁绑定
            rec["impact"] = "按材质排序可减少纹理绑定开销"
        else:
            rec["impact"] = f"预计影响评分: {issue.impact_score:.0f}/100"
        
        return rec


# ============================================================================
# 工厂函数
# ============================================================================

def create_performance_analyzer(context: AnalysisContext) -> PerformanceAnalyzer:
    """创建性能分析器实例"""
    return PerformanceAnalyzer(context)
