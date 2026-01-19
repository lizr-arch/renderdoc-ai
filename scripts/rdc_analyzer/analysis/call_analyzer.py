"""
调用级分析器
============

对每个 Draw Call 的管线状态进行深度分析，检测常见问题和最佳实践违规。

职责：
1. 分析单个 DrawCallDetail 的管线状态
2. 检测跨调用的冗余绑定
3. 生成详细的问题诊断报告
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Callable, Any, Iterator, Tuple
from enum import Enum
import hashlib

from ..core.pipeline_state import (
    DrawCallDetail,
    PipelineSnapshot,
    ShaderBindings,
    ResourceBinding,
    RenderTargetInfo,
    DepthStencilInfo,
    SamplerInfo,
    ShaderStage,
    DrawType,
    ResourceType,
    PrimitiveTopology,
)


class IssueSeverity(Enum):
    """问题严重程度"""
    INFO = "info"          # 仅供参考
    WARNING = "warning"    # 可能的问题
    ERROR = "error"        # 明确的问题
    CRITICAL = "critical"  # 严重问题


class IssueCategory(Enum):
    """问题分类"""
    BINDING = "binding"           # 资源绑定相关
    REDUNDANCY = "redundancy"     # 冗余操作
    PERFORMANCE = "performance"   # 性能问题
    CORRECTNESS = "correctness"   # 正确性问题
    BEST_PRACTICE = "best_practice"  # 最佳实践


@dataclass
class BindingIssue:
    """
    绑定问题描述
    
    记录在分析过程中发现的单个问题
    """
    rule_id: str           # 规则标识符, e.g., "BIND001"
    severity: IssueSeverity
    category: IssueCategory
    event_id: int          # 发生问题的事件ID
    message: str           # 人类可读的描述
    details: Dict[str, Any] = field(default_factory=dict)  # 额外详情
    suggestion: str = ""   # 修复建议
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'rule_id': self.rule_id,
            'severity': self.severity.value,
            'category': self.category.value,
            'event_id': self.event_id,
            'message': self.message,
            'details': self.details,
            'suggestion': self.suggestion,
        }


@dataclass
class BindingState:
    """
    跟踪单个绑定槽位的历史状态
    
    用于检测冗余绑定
    """
    resource_id: int = 0
    binding_hash: str = ""  # 绑定配置的哈希
    last_bound_event: int = 0
    bind_count: int = 0     # 连续绑定次数（未使用时）
    used_since_bind: bool = False  # 绑定后是否被使用


@dataclass 
class CallAnalyzerConfig:
    """分析器配置"""
    # 检测选项
    detect_redundant_bindings: bool = True   # 检测冗余绑定
    detect_null_bindings: bool = True        # 检测空绑定
    detect_excessive_slots: bool = True      # 检测过多槽位使用
    detect_mismatched_formats: bool = True   # 检测格式不匹配
    
    # 阈值
    max_vertex_buffers: int = 8      # 超过此数量视为过多
    max_render_targets: int = 4      # 超过此数量视为过多
    max_texture_slots: int = 16      # 超过此数量视为过多
    redundant_bind_threshold: int = 3  # 连续冗余绑定阈值
    
    # 过滤
    enabled_rules: Set[str] = field(default_factory=set)   # 空=全部启用
    disabled_rules: Set[str] = field(default_factory=set)  # 禁用的规则


class CallAnalyzer:
    """
    调用级分析器
    
    分析 DrawCallDetail 流，检测问题并生成诊断报告。
    
    使用方法：
        analyzer = CallAnalyzer()
        for draw in draw_calls:
            issues = analyzer.analyze(draw)
            for issue in issues:
                print(issue)
        
        # 获取跨调用的问题
        summary_issues = analyzer.finalize()
    """
    
    def __init__(self, config: Optional[CallAnalyzerConfig] = None):
        """初始化分析器"""
        self.config = config or CallAnalyzerConfig()
        
        # 状态跟踪
        self._previous_snapshot: Optional[PipelineSnapshot] = None
        self._binding_history: Dict[str, BindingState] = {}  # key: "stage:type:slot"
        self._analyzed_count: int = 0
        self._total_issues: List[BindingIssue] = []
        
        # 统计
        self._redundant_binds: int = 0
        self._null_binds: int = 0
        self._draw_count: int = 0
        
        # 规则注册表
        self._rules: List[Callable[[DrawCallDetail, Optional[PipelineSnapshot]], List[BindingIssue]]] = []
        self._register_default_rules()
    
    def _register_default_rules(self) -> None:
        """注册默认分析规则"""
        self._rules = [
            self._check_null_vertex_buffer,      # BIND001
            self._check_null_index_buffer,       # BIND002
            self._check_null_shader,             # BIND003
            self._check_null_render_target,      # BIND004
            self._check_excessive_vertex_buffers,  # BIND005
            self._check_excessive_render_targets,  # BIND006
            self._check_redundant_bindings,      # BIND007
            self._check_primitive_topology,      # BIND008
        ]
    
    def _is_rule_enabled(self, rule_id: str) -> bool:
        """检查规则是否启用"""
        if rule_id in self.config.disabled_rules:
            return False
        if self.config.enabled_rules and rule_id not in self.config.enabled_rules:
            return False
        return True
    
    def analyze(self, draw: DrawCallDetail) -> List[BindingIssue]:
        """
        分析单个 Draw Call
        
        Args:
            draw: 要分析的绘制调用详情
            
        Returns:
            发现的问题列表
        """
        issues: List[BindingIssue] = []
        
        # 执行所有规则
        for rule in self._rules:
            try:
                rule_issues = rule(draw, self._previous_snapshot)
                issues.extend(rule_issues)
            except Exception as e:
                # 规则执行失败，记录但继续
                issues.append(BindingIssue(
                    rule_id="INTERNAL",
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.CORRECTNESS,
                    event_id=draw.event_id,
                    message=f"Rule execution failed: {e}",
                ))
        
        # 更新状态
        self._update_binding_history(draw)
        self._previous_snapshot = draw.pipeline
        self._analyzed_count += 1
        if draw.draw_type != DrawType.OTHER:
            self._draw_count += 1
        
        # 收集所有问题
        self._total_issues.extend(issues)
        
        return issues
    
    def analyze_batch(self, draws: Iterator[DrawCallDetail]) -> Iterator[Tuple[DrawCallDetail, List[BindingIssue]]]:
        """
        批量分析多个 Draw Call
        
        Yields:
            (draw, issues) 元组
        """
        for draw in draws:
            issues = self.analyze(draw)
            yield draw, issues
    
    def finalize(self) -> List[BindingIssue]:
        """
        完成分析，返回汇总问题
        
        Returns:
            跨调用检测到的问题（如持续的冗余绑定）
        """
        summary_issues: List[BindingIssue] = []
        
        # 检查持续冗余绑定
        for key, state in self._binding_history.items():
            if state.bind_count >= self.config.redundant_bind_threshold:
                if not state.used_since_bind:
                    summary_issues.append(BindingIssue(
                        rule_id="BIND007",
                        severity=IssueSeverity.WARNING,
                        category=IssueCategory.REDUNDANCY,
                        event_id=state.last_bound_event,
                        message=f"Binding {key} was rebound {state.bind_count} times without being used",
                        details={'binding_key': key, 'bind_count': state.bind_count},
                        suggestion="Consider caching this binding state",
                    ))
        
        self._total_issues.extend(summary_issues)
        return summary_issues
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取分析统计"""
        severity_counts = {}
        category_counts = {}
        rule_counts = {}
        
        for issue in self._total_issues:
            # 按严重程度统计
            sev = issue.severity.value
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
            
            # 按类别统计
            cat = issue.category.value
            category_counts[cat] = category_counts.get(cat, 0) + 1
            
            # 按规则统计
            rule_counts[issue.rule_id] = rule_counts.get(issue.rule_id, 0) + 1
        
        return {
            'analyzed_calls': self._analyzed_count,
            'draw_calls': self._draw_count,
            'total_issues': len(self._total_issues),
            'redundant_binds': self._redundant_binds,
            'null_binds': self._null_binds,
            'by_severity': severity_counts,
            'by_category': category_counts,
            'by_rule': rule_counts,
        }
    
    def reset(self) -> None:
        """重置分析器状态"""
        self._previous_snapshot = None
        self._binding_history.clear()
        self._analyzed_count = 0
        self._total_issues.clear()
        self._redundant_binds = 0
        self._null_binds = 0
        self._draw_count = 0
    
    # ========== 规则实现 ==========
    
    def _check_null_vertex_buffer(
        self, 
        draw: DrawCallDetail, 
        prev: Optional[PipelineSnapshot]
    ) -> List[BindingIssue]:
        """BIND001: 检测空顶点缓冲区"""
        if not self._is_rule_enabled("BIND001"):
            return []
        
        issues = []
        
        # 只对实际绘制调用检查
        if draw.draw_type in (DrawType.DRAW, DrawType.DRAW_INDEXED, 
                              DrawType.DRAW_INSTANCED, DrawType.DRAW_INDEXED_INSTANCED):
            if not draw.pipeline.vertex_buffers:
                issues.append(BindingIssue(
                    rule_id="BIND001",
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.BINDING,
                    event_id=draw.event_id,
                    message="Draw call with no vertex buffers bound",
                    suggestion="Ensure vertex buffer is bound before draw call, "
                               "or use vertex pulling from structured buffer",
                ))
                self._null_binds += 1
        
        return issues
    
    def _check_null_index_buffer(
        self, 
        draw: DrawCallDetail, 
        prev: Optional[PipelineSnapshot]
    ) -> List[BindingIssue]:
        """BIND002: 检测索引绘制无索引缓冲区"""
        if not self._is_rule_enabled("BIND002"):
            return []
        
        issues = []
        
        if draw.draw_type in (DrawType.DRAW_INDEXED, DrawType.DRAW_INDEXED_INSTANCED):
            ib = draw.pipeline.index_buffer
            if ib is None or ib.resource_id == 0:
                issues.append(BindingIssue(
                    rule_id="BIND002",
                    severity=IssueSeverity.ERROR,
                    category=IssueCategory.CORRECTNESS,
                    event_id=draw.event_id,
                    message="Indexed draw call with no index buffer bound",
                    suggestion="Bind an index buffer before DrawIndexed calls",
                ))
                self._null_binds += 1
        
        return issues
    
    def _check_null_shader(
        self, 
        draw: DrawCallDetail, 
        prev: Optional[PipelineSnapshot]
    ) -> List[BindingIssue]:
        """BIND003: 检测缺失着色器"""
        if not self._is_rule_enabled("BIND003"):
            return []
        
        issues = []
        
        # 图形绘制调用需要 VS 和 PS
        if draw.draw_type in (DrawType.DRAW, DrawType.DRAW_INDEXED,
                              DrawType.DRAW_INSTANCED, DrawType.DRAW_INDEXED_INSTANCED):
            vs = draw.pipeline.vertex_shader
            if vs is None or vs.resource_id == 0:
                issues.append(BindingIssue(
                    rule_id="BIND003",
                    severity=IssueSeverity.ERROR,
                    category=IssueCategory.CORRECTNESS,
                    event_id=draw.event_id,
                    message="Draw call with no vertex shader bound",
                ))
            
            ps = draw.pipeline.pixel_shader
            if ps is None or ps.resource_id == 0:
                issues.append(BindingIssue(
                    rule_id="BIND003",
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.BINDING,
                    event_id=draw.event_id,
                    message="Draw call with no pixel shader bound (depth-only pass?)",
                    suggestion="If this is not a depth-only pass, bind a pixel shader",
                ))
        
        # Compute 需要 CS
        if draw.draw_type == DrawType.DISPATCH:
            cs = draw.pipeline.compute_shader
            if cs is None or cs.resource_id == 0:
                issues.append(BindingIssue(
                    rule_id="BIND003",
                    severity=IssueSeverity.ERROR,
                    category=IssueCategory.CORRECTNESS,
                    event_id=draw.event_id,
                    message="Dispatch call with no compute shader bound",
                ))
        
        return issues
    
    def _check_null_render_target(
        self, 
        draw: DrawCallDetail, 
        prev: Optional[PipelineSnapshot]
    ) -> List[BindingIssue]:
        """BIND004: 检测无渲染目标"""
        if not self._is_rule_enabled("BIND004"):
            return []
        
        issues = []
        
        if draw.draw_type in (DrawType.DRAW, DrawType.DRAW_INDEXED,
                              DrawType.DRAW_INSTANCED, DrawType.DRAW_INDEXED_INSTANCED):
            has_rt = any(rt.resource_id != 0 for rt in draw.pipeline.render_targets)
            has_ds = draw.pipeline.depth_stencil and draw.pipeline.depth_stencil.resource_id != 0
            
            if not has_rt and not has_ds:
                issues.append(BindingIssue(
                    rule_id="BIND004",
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.BINDING,
                    event_id=draw.event_id,
                    message="Draw call with no render targets or depth buffer bound",
                    suggestion="This draw call produces no output",
                ))
        
        return issues
    
    def _check_excessive_vertex_buffers(
        self, 
        draw: DrawCallDetail, 
        prev: Optional[PipelineSnapshot]
    ) -> List[BindingIssue]:
        """BIND005: 检测过多顶点缓冲区"""
        if not self._is_rule_enabled("BIND005"):
            return []
        
        issues = []
        
        vb_count = len(draw.pipeline.vertex_buffers)
        if vb_count > self.config.max_vertex_buffers:
            issues.append(BindingIssue(
                rule_id="BIND005",
                severity=IssueSeverity.INFO,
                category=IssueCategory.PERFORMANCE,
                event_id=draw.event_id,
                message=f"Using {vb_count} vertex buffers (threshold: {self.config.max_vertex_buffers})",
                details={'count': vb_count, 'threshold': self.config.max_vertex_buffers},
                suggestion="Consider interleaving vertex attributes to reduce buffer count",
            ))
        
        return issues
    
    def _check_excessive_render_targets(
        self, 
        draw: DrawCallDetail, 
        prev: Optional[PipelineSnapshot]
    ) -> List[BindingIssue]:
        """BIND006: 检测过多渲染目标"""
        if not self._is_rule_enabled("BIND006"):
            return []
        
        issues = []
        
        rt_count = sum(1 for rt in draw.pipeline.render_targets if rt.resource_id != 0)
        if rt_count > self.config.max_render_targets:
            issues.append(BindingIssue(
                rule_id="BIND006",
                severity=IssueSeverity.INFO,
                category=IssueCategory.PERFORMANCE,
                event_id=draw.event_id,
                message=f"Using {rt_count} render targets (threshold: {self.config.max_render_targets})",
                details={'count': rt_count, 'threshold': self.config.max_render_targets},
                suggestion="Consider packing data or using multiple passes for bandwidth",
            ))
        
        return issues
    
    def _check_redundant_bindings(
        self, 
        draw: DrawCallDetail, 
        prev: Optional[PipelineSnapshot]
    ) -> List[BindingIssue]:
        """BIND007: 检测冗余绑定"""
        if not self._is_rule_enabled("BIND007"):
            return []
        if prev is None:
            return []
        
        issues = []
        
        # 比较着色器绑定
        def check_shader_redundant(curr: Optional[ShaderBindings], 
                                   prev_shader: Optional[ShaderBindings],
                                   stage_name: str) -> None:
            if curr and prev_shader:
                if curr.resource_id == prev_shader.resource_id and curr.resource_id != 0:
                    # 着色器相同，检查 CB/SRV/Sampler 是否也相同
                    curr_hash = self._hash_shader_bindings(curr)
                    prev_hash = self._hash_shader_bindings(prev_shader)
                    if curr_hash == prev_hash:
                        self._redundant_binds += 1
        
        # 检查各着色器阶段
        check_shader_redundant(draw.pipeline.vertex_shader, prev.vertex_shader, "VS")
        check_shader_redundant(draw.pipeline.pixel_shader, prev.pixel_shader, "PS")
        check_shader_redundant(draw.pipeline.geometry_shader, prev.geometry_shader, "GS")
        check_shader_redundant(draw.pipeline.hull_shader, prev.hull_shader, "HS")
        check_shader_redundant(draw.pipeline.domain_shader, prev.domain_shader, "DS")
        check_shader_redundant(draw.pipeline.compute_shader, prev.compute_shader, "CS")
        
        return issues  # 冗余绑定在 finalize() 中汇总报告
    
    def _check_primitive_topology(
        self, 
        draw: DrawCallDetail, 
        prev: Optional[PipelineSnapshot]
    ) -> List[BindingIssue]:
        """BIND008: 检测图元拓扑问题"""
        if not self._is_rule_enabled("BIND008"):
            return []
        
        issues = []
        
        if draw.draw_type in (DrawType.DRAW, DrawType.DRAW_INDEXED,
                              DrawType.DRAW_INSTANCED, DrawType.DRAW_INDEXED_INSTANCED):
            topology = draw.pipeline.primitive_topology
            if topology == PrimitiveTopology.UNDEFINED:
                issues.append(BindingIssue(
                    rule_id="BIND008",
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.CORRECTNESS,
                    event_id=draw.event_id,
                    message="Draw call with undefined primitive topology",
                    suggestion="Set IASetPrimitiveTopology before drawing",
                ))
        
        return issues
    
    # ========== 辅助方法 ==========
    
    def _hash_shader_bindings(self, shader: ShaderBindings) -> str:
        """计算着色器绑定配置的哈希"""
        components = [str(shader.resource_id)]
        
        for cb in shader.constant_buffers:
            components.append(f"cb{cb.slot}:{cb.resource_id}")
        for srv in shader.shader_resources:
            components.append(f"srv{srv.slot}:{srv.resource_id}")
        for sampler in shader.samplers:
            components.append(f"samp{sampler.slot}:{sampler.resource_id}")
        
        return hashlib.md5("|".join(components).encode()).hexdigest()[:16]
    
    def _update_binding_history(self, draw: DrawCallDetail) -> None:
        """更新绑定历史记录"""
        snapshot = draw.pipeline
        
        # 跟踪着色器绑定
        def track_shader(shader: Optional[ShaderBindings], stage: str) -> None:
            if shader is None:
                return
            key = f"{stage}:shader"
            current_hash = self._hash_shader_bindings(shader)
            
            if key in self._binding_history:
                state = self._binding_history[key]
                if state.binding_hash == current_hash:
                    state.bind_count += 1
                else:
                    state.binding_hash = current_hash
                    state.resource_id = shader.resource_id
                    state.bind_count = 1
                    state.used_since_bind = False
                state.last_bound_event = draw.event_id
            else:
                self._binding_history[key] = BindingState(
                    resource_id=shader.resource_id,
                    binding_hash=current_hash,
                    last_bound_event=draw.event_id,
                    bind_count=1,
                    used_since_bind=False,
                )
        
        track_shader(snapshot.vertex_shader, "VS")
        track_shader(snapshot.pixel_shader, "PS")
        track_shader(snapshot.geometry_shader, "GS")
        track_shader(snapshot.hull_shader, "HS")
        track_shader(snapshot.domain_shader, "DS")
        track_shader(snapshot.compute_shader, "CS")


# ============ 便捷函数 ============

def analyze_draw_calls(
    draws: List[DrawCallDetail],
    config: Optional[CallAnalyzerConfig] = None
) -> Tuple[List[BindingIssue], Dict[str, Any]]:
    """
    分析一系列 Draw Call
    
    Args:
        draws: DrawCallDetail 列表
        config: 分析器配置
        
    Returns:
        (所有问题列表, 统计信息字典)
    """
    analyzer = CallAnalyzer(config)
    
    for draw in draws:
        analyzer.analyze(draw)
    
    analyzer.finalize()
    
    return analyzer._total_issues, analyzer.get_statistics()


def create_sample_draws_for_testing() -> List[DrawCallDetail]:
    """创建测试用的 DrawCallDetail 列表"""
    draws = []
    
    # Draw 1: 正常绘制
    draws.append(DrawCallDetail(
        event_id=100,
        name="DrawIndexed",
        draw_type=DrawType.DRAW_INDEXED,
        pipeline=PipelineSnapshot(
            primitive_topology=PrimitiveTopology.TRIANGLE_LIST,
            vertex_buffers=[ResourceBinding(
                slot=0, 
                stage=ShaderStage.VERTEX,
                resource_id=1001, 
                stride=32, 
                offset=0,
                resource_type=ResourceType.BUFFER,
            )],
            index_buffer=ResourceBinding(
                slot=0,
                stage=ShaderStage.VERTEX,
                resource_id=1002, 
                format="R16_UINT", 
                offset=0,
                resource_type=ResourceType.BUFFER,
            ),
            vertex_shader=ShaderBindings(
                stage=ShaderStage.VERTEX,
                resource_id=2001,
                name="VSMain",
            ),
            pixel_shader=ShaderBindings(
                stage=ShaderStage.PIXEL,
                resource_id=2002,
                name="PSMain",
            ),
            render_targets=[RenderTargetInfo(
                slot=0, 
                resource_id=3001, 
                format="R8G8B8A8_UNORM",
                width=1920,
                height=1080,
            )],
            depth_stencil=DepthStencilInfo(
                resource_id=3002, 
                format="D24_UNORM_S8_UINT",
                width=1920,
                height=1080,
            ),
        ),
        vertex_count=0,
        index_count=3000,
        instance_count=1,
    ))
    
    # Draw 2: 缺少索引缓冲区的 DrawIndexed (错误)
    draws.append(DrawCallDetail(
        event_id=101,
        name="DrawIndexed",
        draw_type=DrawType.DRAW_INDEXED,
        pipeline=PipelineSnapshot(
            primitive_topology=PrimitiveTopology.TRIANGLE_LIST,
            vertex_buffers=[ResourceBinding(
                slot=0,
                stage=ShaderStage.VERTEX, 
                resource_id=1001, 
                stride=32, 
                offset=0,
                resource_type=ResourceType.BUFFER,
            )],
            index_buffer=None,  # 错误: 无索引缓冲区
            vertex_shader=ShaderBindings(
                stage=ShaderStage.VERTEX,
                resource_id=2001,
                name="VSMain",
            ),
            pixel_shader=ShaderBindings(
                stage=ShaderStage.PIXEL,
                resource_id=2002,
                name="PSMain",
            ),
            render_targets=[RenderTargetInfo(
                slot=0, 
                resource_id=3001, 
                format="R8G8B8A8_UNORM",
                width=1920,
                height=1080,
            )],
        ),
        vertex_count=0,
        index_count=3000,
        instance_count=1,
    ))
    
    # Draw 3: 无顶点着色器 (错误)
    draws.append(DrawCallDetail(
        event_id=102,
        name="Draw",
        draw_type=DrawType.DRAW,
        pipeline=PipelineSnapshot(
            primitive_topology=PrimitiveTopology.TRIANGLE_LIST,
            vertex_buffers=[ResourceBinding(
                slot=0,
                stage=ShaderStage.VERTEX, 
                resource_id=1001, 
                stride=32, 
                offset=0,
                resource_type=ResourceType.BUFFER,
            )],
            vertex_shader=None,  # 错误: 无顶点着色器
            pixel_shader=ShaderBindings(
                stage=ShaderStage.PIXEL,
                resource_id=2002,
                name="PSMain",
            ),
            render_targets=[RenderTargetInfo(
                slot=0, 
                resource_id=3001, 
                format="R8G8B8A8_UNORM",
                width=1920,
                height=1080,
            )],
        ),
        vertex_count=100,
        instance_count=1,
    ))
    
    return draws