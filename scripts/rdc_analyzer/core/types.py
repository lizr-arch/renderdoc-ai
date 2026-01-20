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
    """纹理分析结果"""
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
        thresholds={"max_overdraw": 4}  # 超过 4 次绘制视为问题
    ),
    "PERF002": PerformanceRule(
        rule_id="PERF002",
        name="状态冗余",
        description="检测连续设置相同状态的情况",
        category="state",
        severity="info",
        thresholds={"min_redundant_count": 3}  # 连续 3 次以上视为问题
    ),
    "PERF003": PerformanceRule(
        rule_id="PERF003",
        name="小批次绘制",
        description="检测顶点数过少的绘制调用",
        category="batch",
        severity="warning",
        thresholds={"min_vertices": 100, "min_triangles": 30}
    ),
    "PERF004": PerformanceRule(
        rule_id="PERF004",
        name="大纹理",
        description="检测超过阈值的大纹理",
        category="texture",
        severity="warning",
        thresholds={"max_dimension": 4096, "max_memory_mb": 64}
    ),
    "PERF005": PerformanceRule(
        rule_id="PERF005",
        name="未压缩纹理",
        description="检测未使用压缩格式的纹理",
        category="texture",
        severity="info",
        thresholds={"min_size_for_compression": 256}  # 256x256 以上应压缩
    ),
    "PERF006": PerformanceRule(
        rule_id="PERF006",
        name="Alpha混合过度使用",
        description="检测过多的 Alpha 混合绘制",
        category="blend",
        severity="warning",
        thresholds={"max_blend_ratio": 0.5}  # 超过 50% 的 Draw 使用混合
    ),
    "PERF007": PerformanceRule(
        rule_id="PERF007",
        name="频繁绑定",
        description="检测资源频繁绑定/解绑的情况",
        category="binding",
        severity="info",
        thresholds={"max_rebind_count": 10}  # 同一资源绑定超过 10 次
    ),
}
