"""
核心数据类型定义
================

包含所有资源和分析数据的数据类定义。
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


@dataclass
class TextureInfo:
    """纹理信息"""
    resource_id: str
    name: str = ""
    width: int = 0
    height: int = 0
    depth: int = 1
    array_size: int = 1
    mip_levels: int = 1
    format: str = ""
    format_category: str = ""  # compressed | uncompressed | depth
    sample_count: int = 1
    usage: List[str] = field(default_factory=list)
    memory_size: int = 0  # 字节
    is_render_target: bool = False
    is_depth_stencil: bool = False
    bind_count: int = 0  # 被绑定的次数
    issues: List[str] = field(default_factory=list)


@dataclass
class BufferInfo:
    """缓冲区信息"""
    resource_id: str
    name: str = ""
    size: int = 0  # 字节
    usage: List[str] = field(default_factory=list)
    cpu_access: str = "none"
    stride: int = 0
    element_count: int = 0
    is_dynamic: bool = False
    is_constant_buffer: bool = False
    bind_count: int = 0
    issues: List[str] = field(default_factory=list)


@dataclass
class ShaderConstant:
    """Shader 常量块中的单个变量"""
    name: str = ""
    type_name: str = ""  # float, float4, matrix, etc.
    byte_offset: int = 0
    byte_size: int = 0
    rows: int = 1
    columns: int = 1
    array_size: int = 0  # 0 表示非数组


@dataclass
class ShaderConstantBlock:
    """Shader 常量块 (Constant Buffer)"""
    name: str = ""
    slot: int = 0  # 绑定槽位
    byte_size: int = 0
    variables: List[ShaderConstant] = field(default_factory=list)


@dataclass 
class ShaderResource:
    """Shader 资源绑定 (纹理/Buffer)"""
    name: str = ""
    slot: int = 0
    resource_type: str = ""  # Texture2D | Buffer | StructuredBuffer | etc.
    is_read_only: bool = True


@dataclass
class ShaderSignature:
    """Shader 输入/输出签名参数"""
    semantic_name: str = ""
    semantic_index: int = 0
    var_name: str = ""  # 可选变量名
    register: int = 0
    system_value: str = ""  # SV_Position, SV_Target, etc.
    component_type: str = ""  # float, int, uint
    component_count: int = 4  # 1-4
    used_mask: int = 0xF  # 哪些分量被使用


@dataclass
class ShaderInfo:
    """Shader 完整信息 (扩展版)"""
    resource_id: str
    type: str = ""  # VS | PS | GS | HS | DS | CS | AS | MS (Amplification/Mesh for D3D12)
    name: str = ""
    bind_count: int = 0
    hash: str = ""
    
    # === B.1 扩展字段 ===
    # 阶段标识
    stage: str = ""  # Vertex | Pixel | Geometry | Hull | Domain | Compute | etc.
    
    # 入口点
    entry_point: str = ""
    
    # 源码内容 (可能为空)
    source_hlsl: str = ""  # HLSL 源码 (如果可用)
    source_asm: str = ""  # 反汇编代码 (DXBC/DXIL/SPIR-V)
    
    # 调试信息
    debug_file: str = ""  # 原始源文件路径 (如果嵌入)
    has_debug_info: bool = False
    
    # 编码格式
    encoding: str = ""  # HLSL | DXBC | DXIL | SPIRV | GLSL
    
    # 工作组大小 (仅 Compute)
    workgroup_size: List[int] = field(default_factory=lambda: [0, 0, 0])
    
    # 输入输出签名
    input_signature: List[ShaderSignature] = field(default_factory=list)
    output_signature: List[ShaderSignature] = field(default_factory=list)
    
    # 资源绑定
    constant_blocks: List[ShaderConstantBlock] = field(default_factory=list)
    read_only_resources: List[ShaderResource] = field(default_factory=list)  # SRV (纹理)
    read_write_resources: List[ShaderResource] = field(default_factory=list)  # UAV
    samplers: List[str] = field(default_factory=list)  # 采样器名称列表
    
    # 原始字节数据 (用于 hash 计算，不导出)
    raw_bytes: bytes = field(default_factory=bytes, repr=False)


# 保持向后兼容的简化版本
@dataclass
class ShaderInfoBasic:
    """Shader 基础信息 (向后兼容)"""
    resource_id: str
    type: str = ""  # VS | PS | GS | HS | DS | CS
    name: str = ""
    bind_count: int = 0
    hash: str = ""


@dataclass
class PassInfo:
    """渲染 Pass 信息"""
    index: int
    name: str = ""
    start_event_id: int = 0
    end_event_id: int = 0
    draw_count: int = 0
    dispatch_count: int = 0
    clear_count: int = 0  # Clear 操作数
    render_targets: List["TextureInfo"] = field(default_factory=list)
    depth_stencil: Optional["TextureInfo"] = None
    viewport_width: int = 0
    viewport_height: int = 0
    total_vertices: int = 0
    total_triangles: int = 0
    is_fullscreen: bool = False  # 是否是全屏 Pass (后处理)
    is_depth_only: bool = False  # 是否是 Depth-only Pass
    has_clear: bool = False  # 是否有 Clear 操作
    uses_scissor: bool = False  # 是否使用 Scissor
    marker_name: str = ""  # Debug Marker 名称
    # === P2: Tile/RenderPass 扩展 ===
    color_attachments: List[Dict[str, Any]] = field(default_factory=list)
    depth_attachment: Optional[Dict[str, Any]] = None
    sample_count: int = 1
    has_resolve: bool = False
    has_transient_attachment: bool = False


# 兼容别名
RenderPassInfo = PassInfo


@dataclass
class DrawCallInfo:
    """绘制调用信息"""
    event_id: int
    name: str = ""  # Draw call 名称 (如 "DrawIndexed")
    type: str = ""
    index_count: int = 0
    vertex_count: int = 0
    instance_count: int = 1
    pass_index: int = 0
    # 绑定状态快照
    vs_id: str = ""
    ps_id: str = ""
    rt_ids: List[str] = field(default_factory=list)
    ds_id: str = ""
    # 状态
    blend_enabled: bool = False
    depth_write: bool = True
    depth_test: bool = True
    cull_mode: str = "back"  # none | front | back
    fill_mode: str = "solid"  # solid | wireframe


@dataclass
class Issue:
    """检测到的问题"""
    severity: str  # critical | warning | info
    category: str  # performance | memory | correctness
    code: str  # 规则 ID
    message: str
    threshold: Optional[Any] = None
    actual: Optional[Any] = None
    resource_id: Optional[str] = None
    event_id: Optional[int] = None  # 关联的事件 ID
    suggestion: Optional[str] = None
    # 定位路径 (用于快速跳转)
    location_path: Optional[str] = None  # 如 "Pass 3 > Event 245 > Texture 0x1234"
    
    def to_canonical(self) -> 'CanonicalIssue':
        """转换为 CanonicalIssue 格式"""
        return CanonicalIssue(
            code=self.code,
            severity=self.severity,
            category=self.category,
            message=self.message,
            event_ids=[self.event_id] if self.event_id is not None else [],
            resource_ids=[self.resource_id] if self.resource_id else [],
            evidence={
                'threshold': self.threshold,
                'actual': self.actual,
                'location_path': self.location_path,
            } if self.threshold is not None or self.actual is not None else {},
            suggestion=self.suggestion,
        )


@dataclass
class CanonicalIssue:
    """
    规范化 Issue 格式 (Canonical Schema v1.0)
    
    所有 Issue 类型（Issue, PerformanceIssue, RTIssue, BindingIssue）
    都应能转换为此格式，确保 JSON 输出一致性。
    
    字段说明:
        code: 规则 ID (如 BIND001, PERF003, RT001)
        severity: 严重程度 (critical | warning | info)
        category: 类别 (performance | memory | correctness | best_practice)
        message: 人类可读的问题描述
        event_ids: 关联的事件 ID 列表（支持单事件和多事件问题）
        resource_ids: 关联的资源 ID 列表
        evidence: 证据数据（阈值、实际值、影响分数等）
        suggestion: 修复建议
    """
    code: str
    severity: str
    category: str
    message: str
    event_ids: List[int] = field(default_factory=list)
    resource_ids: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    suggestion: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（用于 JSON 输出）"""
        result = {
            'code': self.code,
            'severity': self.severity,
            'category': self.category,
            'message': self.message,
        }
        
        # 只包含非空字段
        if self.event_ids:
            result['event_ids'] = self.event_ids
        if self.resource_ids:
            result['resource_ids'] = self.resource_ids
        if self.evidence:
            # 过滤掉 None 值
            filtered_evidence = {k: v for k, v in self.evidence.items() if v is not None}
            if filtered_evidence:
                result['evidence'] = filtered_evidence
        if self.suggestion:
            result['suggestion'] = self.suggestion
        
        return result


@dataclass
class FrameSummary:
    """帧摘要统计"""
    draw_call_count: int = 0
    dispatch_count: int = 0
    vertex_count: int = 0
    primitive_count: int = 0
    texture_count: int = 0
    buffer_count: int = 0
    pass_count: int = 0
    rt_switches: int = 0
    shader_changes: int = 0
    blend_state_changes: int = 0
    depth_state_changes: int = 0
    rasterizer_changes: int = 0
    redundant_state_sets: int = 0
    total_texture_memory: int = 0  # 字节
    total_buffer_memory: int = 0  # 字节
    viewport_width: int = 0
    viewport_height: int = 0


@dataclass
class ParsedData:
    """解析器输出的原始数据"""
    api: str = ""  # D3D11 | D3D12 | Vulkan | OpenGL
    file_path: str = ""
    draws: List[Dict] = field(default_factory=list)
    dispatches: List[Dict] = field(default_factory=list)
    clears: List[Dict] = field(default_factory=list)
    resources: Dict[str, Dict] = field(default_factory=dict)
    textures: List[Dict] = field(default_factory=list)
    buffers: List[Dict] = field(default_factory=list)
    shaders: List[Dict] = field(default_factory=list)
    render_targets: List[Dict] = field(default_factory=list)
    buffer_updates: List[Dict] = field(default_factory=list)
    markers: List[Dict] = field(default_factory=list)
    # Render pass / attachment metadata (XML parse)
    render_passes: List[Dict] = field(default_factory=list)
    render_pass_infos: Dict[str, Dict] = field(default_factory=dict)
    # 二进制解析特有
    chunks: List[Dict] = field(default_factory=list)
    # API 模式特有 (RenderDoc controller 对象)
    controller: Any = None
    # 元数据
    total_events: int = 0
    capture_time: str = ""
    
    @property
    def draw_calls(self) -> List['DrawCallInfo']:
        """
        draw_calls 属性 (别名到 draws)
        
        用于兼容 PerformanceAnalyzer 等期望 draw_calls 属性的代码。
        将 Dict 格式的 draws 转换为 DrawCallInfo 对象。
        """
        result = []
        for d in self.draws:
            dc = DrawCallInfo(
                event_id=d.get('eid', d.get('event_id', 0)),
                name=d.get('name', ''),
                vertex_count=d.get('vertex_count', d.get('vertexCount', 0)),
                index_count=d.get('index_count', d.get('indexCount', 0)),
                instance_count=d.get('instance_count', d.get('instanceCount', 1)),
                vs_id=d.get('vs_id', d.get('vs', '')),
                ps_id=d.get('ps_id', d.get('ps', '')),
            )
            result.append(dc)
        return result
    
    @property
    def texture_infos(self) -> List['TextureInfo']:
        """
        texture_infos 属性
        
        将 Dict 格式的 textures 转换为 TextureInfo 对象列表。
        用于兼容 PerformanceAnalyzer 等期望 TextureInfo 对象的代码。
        """
        result = []
        for t in self.textures:
            # 处理 Dict 和 TextureInfo 两种输入
            if isinstance(t, dict):
                tex = TextureInfo(
                    resource_id=t.get('id', t.get('resource_id', '')),
                    name=t.get('name', ''),
                    width=t.get('width', 0),
                    height=t.get('height', 0),
                    depth=t.get('depth', 1),
                    array_size=t.get('array_size', t.get('arraySize', 1)),
                    mip_levels=t.get('mip_levels', t.get('mipLevels', 1)),
                    format=t.get('format', ''),
                    format_category=t.get('format_category', ''),
                    sample_count=t.get('sample_count', t.get('sampleCount', 1)),
                    memory_size=t.get('byte_size', t.get('byteSize', t.get('memory_size', 0))),
                    is_render_target=t.get('is_render_target', t.get('isRenderTarget', False)),
                    is_depth_stencil=t.get('is_depth_stencil', t.get('isDepthStencil', False)),
                    bind_count=t.get('bind_count', t.get('bindCount', 0)),
                )
                result.append(tex)
            elif hasattr(t, 'resource_id'):
                # 已经是 TextureInfo 对象
                result.append(t)
        return result


# ============================================================================
# C.1: 性能分析数据模型
# ============================================================================

@dataclass
class PerformanceMetrics:
    """单个 Draw Call 的性能指标"""
    event_id: int
    
    # 几何复杂度
    vertex_count: int = 0
    triangle_count: int = 0
    instance_count: int = 1
    
    # 状态变更统计
    shader_changed: bool = False
    render_target_changed: bool = False
    blend_state_changed: bool = False
    depth_state_changed: bool = False
    rasterizer_state_changed: bool = False
    
    # 资源绑定统计
    texture_bindings: int = 0
    buffer_bindings: int = 0
    constant_buffer_bindings: int = 0
    sampler_bindings: int = 0
    
    # 输出分析
    output_width: int = 0
    output_height: int = 0
    output_pixels: int = 0  # width * height
    render_target_count: int = 0
    uses_depth: bool = False
    uses_stencil: bool = False
    
    # 混合状态
    alpha_blend_enabled: bool = False
    alpha_to_coverage: bool = False
    
    # 估算开销 (0-100)
    estimated_cost: float = 0.0


@dataclass
class PerformanceIssue:
    """性能问题"""
    rule_id: str  # PERF001, PERF002, etc.
    severity: str  # critical | warning | info
    category: str  # overdraw | state | batch | texture | blend | binding
    title: str
    message: str
    
    # 问题位置
    event_id: Optional[int] = None
    event_range: Optional[tuple] = None  # (start_eid, end_eid) 用于范围问题
    resource_id: Optional[str] = None
    pass_index: Optional[int] = None
    
    # 量化数据
    actual_value: Optional[Any] = None
    threshold_value: Optional[Any] = None
    impact_score: float = 0.0  # 影响程度 0-100
    
    # 建议
    suggestion: str = ""
    
    # 相关事件列表 (用于批量问题)
    related_events: List[int] = field(default_factory=list)
    
    # 证据链 (M2.2)
    evidence_chain: Optional['EvidenceChain'] = None
    
    def to_canonical(self) -> 'CanonicalIssue':
        """转换为 CanonicalIssue 格式"""
        # 构建 event_ids 列表
        event_ids = []
        if self.event_id is not None:
            event_ids.append(self.event_id)
        if self.event_range:
            start, end = self.event_range
            if start not in event_ids:
                event_ids.append(start)
            if end not in event_ids:
                event_ids.append(end)
        event_ids.extend([e for e in self.related_events if e not in event_ids])
        
        # 构建 evidence
        evidence = {}
        if self.actual_value is not None:
            evidence['actual'] = self.actual_value
        if self.threshold_value is not None:
            evidence['threshold'] = self.threshold_value
        if self.impact_score > 0:
            evidence['impact_score'] = self.impact_score
        if self.pass_index is not None:
            evidence['pass_index'] = self.pass_index
        if self.title:
            evidence['title'] = self.title
        
        # M2.3: 添加证据链到 evidence
        if self.evidence_chain is not None:
            try:
                evidence['evidence_chain'] = self.evidence_chain.to_dict()
            except Exception:
                pass  # 忽略序列化失败
        
        return CanonicalIssue(
            code=self.rule_id,
            severity=self.severity,
            category=self.category,
            message=self.message,
            event_ids=event_ids,
            resource_ids=[self.resource_id] if self.resource_id else [],
            evidence=evidence,
            suggestion=self.suggestion if self.suggestion else None,
        )


@dataclass
class PerformanceReport:
    """性能分析报告"""
    # 帧级统计
    total_draw_calls: int = 0
    total_dispatches: int = 0
    total_triangles: int = 0
    total_vertices: int = 0
    total_instances: int = 0
    
    # 状态变更统计
    total_shader_changes: int = 0
    total_rt_changes: int = 0
    total_blend_changes: int = 0
    total_depth_changes: int = 0
    total_rasterizer_changes: int = 0
    redundant_state_sets: int = 0
    
    # 资源统计
    unique_textures: int = 0
    unique_buffers: int = 0
    unique_shaders: int = 0
    total_texture_memory_mb: float = 0.0
    total_buffer_memory_mb: float = 0.0
    
    # 问题汇总
    issues: List[PerformanceIssue] = field(default_factory=list)
    
    # 按严重级别统计
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    
    # 按类别统计
    overdraw_issues: int = 0
    state_issues: int = 0
    batch_issues: int = 0
    texture_issues: int = 0
    blend_issues: int = 0
    binding_issues: int = 0
    
    # 性能评分 (0-100, 越高越好)
    overall_score: float = 100.0
    
    # 各指标详情
    metrics_by_event: Dict[int, PerformanceMetrics] = field(default_factory=dict)
    
    # 建议列表 (按优先级排序)
    recommendations: List[str] = field(default_factory=list)
    
    # 纹理分析汇总
    texture_analysis: Optional['TextureAnalysisSummary'] = None
    
    # 批次分析汇总
    batch_analysis: Optional['BatchAnalysisSummary'] = None


@dataclass
class OverdrawInfo:
    """过度绘制信息"""
    pixel_x: int
    pixel_y: int
    draw_count: int  # 该像素被绘制的次数
    related_events: List[int] = field(default_factory=list)


@dataclass
class StateRedundancy:
    """状态冗余信息"""
    state_type: str  # shader | blend | depth | rasterizer | render_target
    first_event_id: int
    second_event_id: int
    state_hash: str = ""  # 状态的哈希值 (用于识别相同状态)


@dataclass
class BatchAnalysis:
    """批次分析结果"""
    event_id: int
    vertex_count: int
    triangle_count: int
    instance_count: int
    is_small_batch: bool = False  # 小批次
    is_instanced: bool = False
    could_be_merged: bool = False  # 是否可以与相邻 Draw 合并
    merge_candidates: List[int] = field(default_factory=list)  # 可合并的事件 ID


@dataclass
class TextureAnalysis:
    """单个纹理的分析结果"""
    resource_id: str
    name: str = ""
    width: int = 0
    height: int = 0
    format: str = ""
    memory_bytes: int = 0
    mip_levels: int = 1
    
    # 问题标记
    is_oversized: bool = False  # 超大纹理
    is_uncompressed: bool = False  # 未压缩
    missing_mipmaps: bool = False  # 缺少 mipmap
    is_power_of_two: bool = True  # 是否是 2 的幂
    
    # 使用统计
    bind_count: int = 0
    used_in_events: List[int] = field(default_factory=list)


@dataclass
class TextureAnalysisSummary:
    """纹理分析汇总结果 (用于 PerformanceReport)"""
    large_textures: List[str] = field(default_factory=list)  # 大纹理名称列表
    uncompressed_textures: List[str] = field(default_factory=list)  # 未压缩纹理名称列表
    npot_textures: List[str] = field(default_factory=list)  # 非2的幂纹理名称列表
    total_large_texture_count: int = 0
    total_uncompressed_count: int = 0
    total_large_texture_memory_mb: float = 0.0


@dataclass
class BatchAnalysisSummary:
    """批次分析汇总结果 (用于 PerformanceReport)"""
    avg_batch_size: float = 0.0  # 平均批次大小 (三角形数)
    small_batch_count: int = 0  # 小批次数量 (< 500 三角形)
    very_small_batch_count: int = 0  # 极小批次数量 (< 100 三角形)
    total_batches: int = 0
    instanced_batch_count: int = 0


# ============================================================================
# 性能规则定义
# ============================================================================

@dataclass
class PerformanceRule:
    """性能规则定义"""
    rule_id: str
    name: str
    description: str
    category: str  # overdraw | state | batch | texture | blend | binding
    severity: str  # critical | warning | info
    suggestion: str = ""  # 优化建议文本
    enabled: bool = True
    
    # 阈值参数 (规则特定)
    thresholds: Dict[str, Any] = field(default_factory=dict)


# 预定义规则集
PERFORMANCE_RULES: Dict[str, PerformanceRule] = {
    "PERF001": PerformanceRule(
        rule_id="PERF001",
        name="过度绘制",
        description="检测同一像素被多次绘制的情况",
        category="overdraw",
        severity="warning",
        suggestion="使用深度预绘制(Z-Prepass)或遮挡剔除减少过度绘制",
        thresholds={"max_overdraw": 4}  # 超过 4 次绘制视为问题
    ),
    "PERF002": PerformanceRule(
        rule_id="PERF002",
        name="状态冗余",
        description="检测连续设置相同状态的情况",
        category="state",
        severity="info",
        suggestion="按材质/Shader排序绘制调用，减少状态切换",
        thresholds={"min_redundant_count": 3}  # 连续 3 次以上视为问题
    ),
    "PERF003": PerformanceRule(
        rule_id="PERF003",
        name="小批次绘制",
        description="检测顶点数过少的绘制调用",
        category="batch",
        severity="warning",
        suggestion="使用GPU实例化或静态批处理合并小绘制调用",
        thresholds={"min_vertices": 100, "min_triangles": 30}
    ),
    "PERF004": PerformanceRule(
        rule_id="PERF004",
        name="大纹理",
        description="检测超过阈值的大纹理",
        category="texture",
        severity="warning",
        suggestion="使用较低分辨率的纹理或虚拟纹理(Virtual Texturing)",
        thresholds={"max_dimension": 4096, "max_memory_mb": 64}
    ),
    "PERF005": PerformanceRule(
        rule_id="PERF005",
        name="未压缩纹理",
        description="检测未使用压缩格式的纹理",
        category="texture",
        severity="info",
        suggestion="使用BC/DXT压缩格式减少显存占用和带宽消耗",
        thresholds={"min_size_for_compression": 256}  # 256x256 以上应压缩
    ),
    "PERF006": PerformanceRule(
        rule_id="PERF006",
        name="Alpha混合过度使用",
        description="检测过多的 Alpha 混合绘制",
        category="blend",
        severity="warning",
        suggestion="减少半透明物体数量或使用Alpha测试代替混合",
        thresholds={"max_blend_ratio": 0.5}  # 超过 50% 的 Draw 使用混合
    ),
    "PERF007": PerformanceRule(
        rule_id="PERF007",
        name="频繁绑定",
        description="检测资源频繁绑定/解绑的情况",
        category="binding",
        severity="info",
        suggestion="使用Bindless资源或合并纹理为图集减少绑定次数",
        thresholds={"max_rebind_count": 10}  # 同一资源绑定超过 10 次
    ),
}


# ============================================================================
# M1: 资源使用索引与证据链数据结构
# ============================================================================

@dataclass
class UsageRecord:
    """
    资源使用记录 (M1.1.1)
    
    记录某个资源在某个事件中的使用情况。
    用于构建资源 → 事件的反向索引。
    
    字段说明:
        event_id: 使用该资源的事件 ID (EID)
        binding_type: 绑定类型 (SRV | UAV | RTV | DSV | CBV | VB | IB)
        slot: 绑定槽位 (如 t0, u1, b2 等)
        purpose_hint: 用途推测 (Albedo | Normal | Shadow | Depth | etc.)
        pass_name: 所属 Pass 名称 (如有)
        draw_name: Draw Call 名称 (如 DrawIndexed)
    """
    event_id: int
    binding_type: str = ""  # SRV | UAV | RTV | DSV | CBV | VB | IB
    slot: int = -1  # 绑定槽位索引
    purpose_hint: str = ""  # Albedo | Normal | Shadow | Depth | RT | DepthStencil
    pass_name: str = ""  # Pass 名称
    draw_name: str = ""  # Draw Call 名称
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {'event_id': self.event_id}
        if self.binding_type:
            result['binding_type'] = self.binding_type
        if self.slot >= 0:
            result['slot'] = self.slot
        if self.purpose_hint:
            result['purpose_hint'] = self.purpose_hint
        if self.pass_name:
            result['pass_name'] = self.pass_name
        if self.draw_name:
            result['draw_name'] = self.draw_name
        return result


@dataclass
class ResourceUsageIndex:
    """
    资源使用索引 (M1.1.2)
    
    存储整帧的资源使用反向索引。
    支持按资源 ID 快速查找其被哪些事件使用。
    
    使用示例:
        index = ResourceUsageIndex()
        index.add_usage("tex_0x1234", UsageRecord(event_id=100, binding_type="SRV", slot=0))
        usages = index.get_usages("tex_0x1234")  # 返回 UsageRecord 列表
    """
    # 纹理使用索引: texture_id -> List[UsageRecord]
    texture_usages: Dict[str, List[UsageRecord]] = field(default_factory=dict)
    
    # Shader 使用索引: shader_id -> List[UsageRecord]
    shader_usages: Dict[str, List[UsageRecord]] = field(default_factory=dict)
    
    # Buffer 使用索引: buffer_id -> List[UsageRecord]
    buffer_usages: Dict[str, List[UsageRecord]] = field(default_factory=dict)
    
    # RT 使用索引: rt_id -> List[UsageRecord] (作为输出目标)
    render_target_usages: Dict[str, List[UsageRecord]] = field(default_factory=dict)
    
    def add_texture_usage(self, resource_id: str, record: UsageRecord) -> None:
        """添加纹理使用记录"""
        if resource_id not in self.texture_usages:
            self.texture_usages[resource_id] = []
        self.texture_usages[resource_id].append(record)
    
    def add_shader_usage(self, resource_id: str, record: UsageRecord) -> None:
        """添加 Shader 使用记录"""
        if resource_id not in self.shader_usages:
            self.shader_usages[resource_id] = []
        self.shader_usages[resource_id].append(record)
    
    def add_buffer_usage(self, resource_id: str, record: UsageRecord) -> None:
        """添加 Buffer 使用记录"""
        if resource_id not in self.buffer_usages:
            self.buffer_usages[resource_id] = []
        self.buffer_usages[resource_id].append(record)
    
    def add_rt_usage(self, resource_id: str, record: UsageRecord) -> None:
        """添加 RenderTarget 使用记录 (作为输出)"""
        if resource_id not in self.render_target_usages:
            self.render_target_usages[resource_id] = []
        self.render_target_usages[resource_id].append(record)
    
    def get_texture_usages(self, resource_id: str) -> List[UsageRecord]:
        """获取纹理的所有使用记录"""
        return self.texture_usages.get(resource_id, [])
    
    def get_shader_usages(self, resource_id: str) -> List[UsageRecord]:
        """获取 Shader 的所有使用记录"""
        return self.shader_usages.get(resource_id, [])
    
    def get_buffer_usages(self, resource_id: str) -> List[UsageRecord]:
        """获取 Buffer 的所有使用记录"""
        return self.buffer_usages.get(resource_id, [])
    
    def get_rt_usages(self, resource_id: str) -> List[UsageRecord]:
        """获取 RenderTarget 的所有使用记录"""
        return self.render_target_usages.get(resource_id, [])
    
    def get_all_usages(self, resource_id: str) -> List[UsageRecord]:
        """获取任意资源的所有使用记录 (搜索所有索引)"""
        usages = []
        usages.extend(self.get_texture_usages(resource_id))
        usages.extend(self.get_shader_usages(resource_id))
        usages.extend(self.get_buffer_usages(resource_id))
        usages.extend(self.get_rt_usages(resource_id))
        return usages
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式 (用于 JSON 输出)"""
        return {
            'texture_usages': {
                k: [r.to_dict() for r in v] 
                for k, v in self.texture_usages.items()
            },
            'shader_usages': {
                k: [r.to_dict() for r in v] 
                for k, v in self.shader_usages.items()
            },
            'buffer_usages': {
                k: [r.to_dict() for r in v] 
                for k, v in self.buffer_usages.items()
            },
            'render_target_usages': {
                k: [r.to_dict() for r in v] 
                for k, v in self.render_target_usages.items()
            },
        }
    
    def get_statistics(self) -> Dict[str, int]:
        """获取统计信息"""
        return {
            'indexed_textures': len(self.texture_usages),
            'indexed_shaders': len(self.shader_usages),
            'indexed_buffers': len(self.buffer_usages),
            'indexed_render_targets': len(self.render_target_usages),
            'total_texture_usages': sum(len(v) for v in self.texture_usages.values()),
            'total_shader_usages': sum(len(v) for v in self.shader_usages.values()),
            'total_buffer_usages': sum(len(v) for v in self.buffer_usages.values()),
            'total_rt_usages': sum(len(v) for v in self.render_target_usages.values()),
        }


# ============================================================================
# M2: 证据链数据结构
# ============================================================================

@dataclass
class Action:
    """
    跳转操作 (M2 配套)
    
    定义 Issue 卡片上的可执行操作（如跳转到事件、查看纹理详情等）。
    
    字段说明:
        type: 操作类型 (jump_to_event | jump_to_texture | jump_to_shader | open_panel)
        label: 按钮显示文本
        target_page: 目标页面 (events.html | textures.html | shaders.html | index.html)
        target_id: 目标元素 ID (如 event_id、texture_id)
        params: 附加参数 (如 highlight=true)
    """
    type: str  # jump_to_event | jump_to_texture | jump_to_shader | open_panel
    label: str = ""
    target_page: str = ""  # events.html | textures.html | shaders.html
    target_id: str = ""  # 目标 ID
    params: Dict[str, Any] = field(default_factory=dict)  # 附加 URL 参数
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {'type': self.type}
        if self.label:
            result['label'] = self.label
        if self.target_page:
            result['target_page'] = self.target_page
        if self.target_id:
            result['target_id'] = self.target_id
        if self.params:
            result['params'] = self.params
        return result
    
    def to_url(self, base_path: str = "") -> str:
        """生成跳转 URL"""
        url = f"{base_path}{self.target_page}" if self.target_page else ""
        params = dict(self.params)
        if self.target_id:
            params['id'] = self.target_id
        if params:
            param_str = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{param_str}" if url else f"?{param_str}"
        return url


@dataclass
class ContextEvidence:
    """
    上下文证据项 (M2 配套)
    
    存储单条证据信息，支持类型化的证据展示。
    
    字段说明:
        type: 证据类型 (metric | resource | state | comparison)
        label: 证据标签 (如 "纹理尺寸")
        value: 实际值
        threshold: 阈值 (可选)
        unit: 单位 (如 "KB", "px", "%")
        severity: 证据严重程度 (normal | warning | critical)
        resource_id: 关联资源 ID (可选)
    """
    type: str  # metric | resource | state | comparison
    label: str
    value: Any
    threshold: Optional[Any] = None
    unit: str = ""
    severity: str = "normal"  # normal | warning | critical
    resource_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {
            'type': self.type,
            'label': self.label,
            'value': self.value,
        }
        if self.threshold is not None:
            result['threshold'] = self.threshold
        if self.unit:
            result['unit'] = self.unit
        if self.severity != "normal":
            result['severity'] = self.severity
        if self.resource_id:
            result['resource_id'] = self.resource_id
        return result


@dataclass
class EvidenceChain:
    """
    证据链 (M2.1)
    
    为每个 Issue 提供完整的证据支持和可执行操作。
    证据链回答三个核心问题：
    1. 为什么这是问题？(evidences)
    2. 影响有多大？(impact_score, affected_resources)
    3. 如何定位和修复？(actions, verification_plan)
    
    字段说明:
        issue_code: 关联的 Issue 规则 ID
        summary: 一句话总结
        evidences: 证据列表
        actions: 可执行操作列表
        affected_resources: 受影响的资源 ID 列表
        affected_events: 受影响的事件 ID 列表
        impact_score: 影响评分 (0-100)
        verification_plan: 验证方案描述
    """
    issue_code: str
    summary: str = ""
    evidences: List[ContextEvidence] = field(default_factory=list)
    actions: List[Action] = field(default_factory=list)
    affected_resources: List[str] = field(default_factory=list)
    affected_events: List[int] = field(default_factory=list)
    impact_score: float = 0.0  # 0-100
    verification_plan: str = ""
    
    def add_evidence(
        self,
        label: str,
        value: Any,
        threshold: Optional[Any] = None,
        unit: str = "",
        evidence_type: str = "metric",
        severity: str = "normal",
        resource_id: Optional[str] = None
    ) -> 'EvidenceChain':
        """添加证据项 (链式调用)"""
        self.evidences.append(ContextEvidence(
            type=evidence_type,
            label=label,
            value=value,
            threshold=threshold,
            unit=unit,
            severity=severity,
            resource_id=resource_id
        ))
        return self
    
    def add_action(
        self,
        action_type: str,
        label: str,
        target_page: str = "",
        target_id: str = "",
        **params
    ) -> 'EvidenceChain':
        """添加操作 (链式调用)"""
        self.actions.append(Action(
            type=action_type,
            label=label,
            target_page=target_page,
            target_id=target_id,
            params=params
        ))
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {
            'issue_code': self.issue_code,
        }
        if self.summary:
            result['summary'] = self.summary
        if self.evidences:
            result['evidences'] = [e.to_dict() for e in self.evidences]
        if self.actions:
            result['actions'] = [a.to_dict() for a in self.actions]
        if self.affected_resources:
            result['affected_resources'] = self.affected_resources
        if self.affected_events:
            result['affected_events'] = self.affected_events
        if self.impact_score > 0:
            result['impact_score'] = self.impact_score
        if self.verification_plan:
            result['verification_plan'] = self.verification_plan
        return result
