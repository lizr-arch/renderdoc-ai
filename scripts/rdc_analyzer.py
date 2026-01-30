#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RDC 自动分析器 v2.0
=====================

使用 RenderDoc Python API 分析 .rdc 文件，生成结构化报告。
实现 RULES_RENDERDOC.md 中定义的检测规则。

支持两种模式:
1. API 模式: 在 RenderDoc 环境中运行，功能完整
2. 二进制模式: 独立运行，基础统计功能

输出:
- JSON 格式的完整分析数据
- Markdown 格式的人类可读报告
- 问题检测和优化建议

用法:
    # 在 RenderDoc 的 Python 环境中运行
    python rdc_analyzer.py <rdc_file>
    
    # 或者在 RenderDoc UI 的 Python Shell 中:
    exec(open('rdc_analyzer.py').read())
    analyze_rdc(r'path/to/capture.rdc')

规则参考: docs/analysis/RULES_RENDERDOC.md
"""

import json
import os
import sys
import struct
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any, Tuple, Set
from datetime import datetime
from collections import defaultdict
from enum import Enum

# 尝试导入 renderdoc 模块
try:
    import renderdoc as rd
    HAS_RENDERDOC = True
except ImportError:
    HAS_RENDERDOC = False
    print("警告: renderdoc 模块不可用，将使用二进制解析模式")

# 尝试导入 lz4 模块（二进制解析模式需要）
try:
    import lz4.block
    HAS_LZ4 = True
except ImportError:
    HAS_LZ4 = False


# =============================================================================
# 规则 ID 定义 (与 RULES_RENDERDOC.md 保持一致)
# =============================================================================

class RuleID:
    """规则 ID 常量 (对应 RULES_RENDERDOC.md)"""
    # Draw Call
    DC_001 = "RD_DC_001"  # HIGH_DRAW_CALL_COUNT
    DC_002 = "RD_DC_002"  # FREQUENT_STATE_SWITCH
    DC_003 = "RD_DC_003"  # UNBATCHED_SAME_MATERIAL
    DC_004 = "RD_DC_004"  # INSTANCING_CANDIDATE
    DC_005 = "RD_DC_005"  # EMPTY_DRAW_CALL
    
    # 纹理
    TEX_001 = "RD_TEX_001"  # LARGE_UNCOMPRESSED_TEXTURE
    TEX_002 = "RD_TEX_002"  # NON_POT_TEXTURE
    TEX_003 = "RD_TEX_003"  # NO_MIPMAP
    TEX_004 = "RD_TEX_004"  # HUGE_TEXTURE
    TEX_005 = "RD_TEX_005"  # HIGH_TEXTURE_MEMORY
    TEX_006 = "RD_TEX_006"  # DUPLICATE_TEXTURE
    
    # 顶点
    VERT_001 = "RD_VERT_001"  # HIGH_VERTEX_COUNT
    VERT_002 = "RD_VERT_002"  # LARGE_SINGLE_DRAW
    VERT_003 = "RD_VERT_003"  # HIGHPOLY_LOD_ISSUE
    VERT_004 = "RD_VERT_004"  # INEFFICIENT_INDEX_FORMAT
    
    # RT
    RT_001 = "RD_RT_001"  # FREQUENT_RT_SWITCH
    RT_002 = "RD_RT_002"  # UNUSED_RT
    RT_003 = "RD_RT_003"  # OVERSIZED_RT
    RT_004 = "RD_RT_004"  # MULTIPLE_RT_CLEAR
    
    # Shader
    SHADER_001 = "RD_SHADER_001"  # FREQUENT_SHADER_SWITCH
    SHADER_002 = "RD_SHADER_002"  # HIGH_SAMPLER_COUNT
    SHADER_003 = "RD_SHADER_003"  # LARGE_CB
    SHADER_004 = "RD_SHADER_004"  # UNUSED_CB_SLOT
    
    # Buffer
    BUF_001 = "RD_BUF_001"  # HIGH_BUFFER_MEMORY
    BUF_002 = "RD_BUF_002"  # LARGE_DYNAMIC_BUFFER
    BUF_003 = "RD_BUF_003"  # UNUSED_BUFFER
    
    # 状态
    STATE_001 = "RD_STATE_001"  # DEPTH_WRITE_WITH_BLEND
    STATE_002 = "RD_STATE_002"  # BACKFACE_CULL_OFF
    STATE_003 = "RD_STATE_003"  # SCISSOR_UNUSED
    STATE_004 = "RD_STATE_004"  # WIREFRAME_MODE
    
    # Overdraw
    OD_001 = "RD_OD_001"  # HIGH_TRANSPARENT_RATIO
    OD_002 = "RD_OD_002"  # TRANSPARENT_UNSORTED
    OD_003 = "RD_OD_003"  # EXCESSIVE_FULLSCREEN_PASS


# =============================================================================
# 数据结构定义
# =============================================================================

@dataclass
class TextureInfo:
    """纹理信息"""
    id: str
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
    memory_bytes: int = 0
    is_render_target: bool = False
    is_depth_stencil: bool = False
    bind_count: int = 0  # 被绑定的次数
    issues: List[str] = field(default_factory=list)


@dataclass
class BufferInfo:
    """缓冲区信息"""
    id: str
    name: str = ""
    size_bytes: int = 0
    usage: List[str] = field(default_factory=list)
    cpu_access: str = "none"
    stride: int = 0
    element_count: int = 0
    is_dynamic: bool = False
    bind_count: int = 0
    issues: List[str] = field(default_factory=list)


@dataclass
class ShaderInfo:
    """Shader 信息"""
    id: str
    type: str = ""  # VS | PS | GS | HS | DS | CS
    name: str = ""
    bind_count: int = 0
    hash: str = ""


@dataclass
class RenderPassInfo:
    """渲染 Pass 信息"""
    index: int
    name: str = ""
    start_event_id: int = 0
    end_event_id: int = 0
    draw_count: int = 0
    dispatch_count: int = 0
    clear_count: int = 0  # Clear 操作数
    render_targets: List[Dict] = field(default_factory=list)
    depth_stencil: Optional[Dict] = None
    viewport_width: int = 0
    viewport_height: int = 0
    total_vertices: int = 0
    total_triangles: int = 0
    is_fullscreen: bool = False  # 是否是全屏 Pass (后处理)
    marker_name: str = ""  # Debug Marker 名称


@dataclass
class DrawCallInfo:
    """绘制调用信息"""
    event_id: int
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
    severity: str  # error | warning | info
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
    """帧级摘要"""
    # 绘制统计
    total_draw_calls: int = 0
    total_dispatches: int = 0
    total_vertices: int = 0
    total_triangles: int = 0
    total_indices: int = 0
    instanced_draws: int = 0
    indirect_draws: int = 0
    
    # 资源统计
    texture_count: int = 0
    buffer_count: int = 0
    shader_count: int = 0
    render_target_count: int = 0
    depth_stencil_count: int = 0
    
    # 内存估算
    estimated_texture_memory_mb: float = 0.0
    estimated_buffer_memory_mb: float = 0.0
    estimated_total_memory_mb: float = 0.0
    
    # 状态切换
    shader_changes: int = 0
    render_target_changes: int = 0
    viewport_changes: int = 0
    blend_state_changes: int = 0
    depth_state_changes: int = 0
    rasterizer_state_changes: int = 0
    
    # 效率指标
    redundant_state_sets: int = 0
    redundant_state_ratio: float = 0.0
    avg_vertices_per_draw: float = 0.0
    small_draw_count: int = 0
    small_draw_ratio: float = 0.0
    
    # 透明物体统计
    transparent_draw_count: int = 0
    transparent_draw_ratio: float = 0.0


@dataclass
class AnalysisResult:
    """完整分析结果"""
    version: str = "2.0"
    meta: Dict = field(default_factory=dict)
    frame_summary: FrameSummary = field(default_factory=FrameSummary)
    textures: List[TextureInfo] = field(default_factory=list)
    buffers: List[BufferInfo] = field(default_factory=list)
    shaders: List[ShaderInfo] = field(default_factory=list)
    render_passes: List[RenderPassInfo] = field(default_factory=list)
    draw_calls: List[DrawCallInfo] = field(default_factory=list)
    state_changes: Dict = field(default_factory=dict)
    issues: List[Issue] = field(default_factory=list)


# =============================================================================
# 问题检测阈值 (基于 RULES_RENDERDOC.md)
# =============================================================================

# PC 平台阈值
THRESHOLDS_PC = {
    # Draw Call
    'draw_call_warning': 2000,
    'draw_call_error': 5000,
    'small_draw_vertices': 100,
    'small_draw_ratio_warning': 0.20,
    'state_switch_ratio_warning': 0.80,  # 80% DC 都切换状态
    'instancing_candidate_threshold': 10,  # 相同 Mesh 出现 10 次
    
    # 纹理
    'texture_uncompressed_size': 1024,  # 1024x1024 以上应压缩
    'texture_huge_size': 4096,
    'texture_memory_warning_mb': 2048,  # 2GB
    'texture_no_mipmap_size': 512,
    
    # 顶点
    'vertex_total_warning': 2_000_000,
    'vertex_single_draw_warning': 65535,
    
    # RT
    'rt_switch_warning': 15,
    'rt_clear_per_target_warning': 2,
    'rt_oversize_ratio': 2.0,  # RT > 屏幕 2x
    
    # Shader
    'sampler_per_shader_warning': 12,
    'srv_per_shader_warning': 24,
    'cb_size_warning': 65536,  # 64KB
    
    # Buffer
    'buffer_memory_warning_mb': 512,
    'dynamic_buffer_size_warning': 1048576,  # 1MB
    
    # 状态
    'redundant_state_warning': 0.10,
    
    # Overdraw
    'transparent_ratio_warning': 0.30,
    'fullscreen_pass_warning': 5,
}

# 移动平台阈值 (更严格)
THRESHOLDS_MOBILE = {
    # Draw Call
    'draw_call_warning': 200,
    'draw_call_error': 500,
    'small_draw_vertices': 50,
    'small_draw_ratio_warning': 0.15,
    'state_switch_ratio_warning': 0.70,
    'instancing_candidate_threshold': 5,
    
    # 纹理
    'texture_uncompressed_size': 512,
    'texture_huge_size': 2048,
    'texture_memory_warning_mb': 512,
    'texture_no_mipmap_size': 256,
    
    # 顶点
    'vertex_total_warning': 500_000,
    'vertex_single_draw_warning': 32768,
    
    # RT
    'rt_switch_warning': 8,
    'rt_clear_per_target_warning': 2,
    'rt_oversize_ratio': 1.5,
    
    # Shader
    'sampler_per_shader_warning': 8,
    'srv_per_shader_warning': 16,
    'cb_size_warning': 16384,  # 16KB
    
    # Buffer
    'buffer_memory_warning_mb': 256,
    'dynamic_buffer_size_warning': 524288,  # 512KB
    
    # 状态
    'redundant_state_warning': 0.05,
    
    # Overdraw
    'transparent_ratio_warning': 0.20,
    'fullscreen_pass_warning': 3,
}


# =============================================================================
# 格式工具函数
# =============================================================================

# 压缩格式列表 (DXGI_FORMAT / VkFormat)
COMPRESSED_FORMATS = {
    'BC1', 'BC2', 'BC3', 'BC4', 'BC5', 'BC6', 'BC7',  # D3D
    'DXT1', 'DXT3', 'DXT5',  # Legacy
    'ETC1', 'ETC2', 'EAC',  # Mobile
    'ASTC', 'PVRTC',  # Mobile
}

# 深度格式列表
DEPTH_FORMATS = {
    'D16', 'D24', 'D32', 'D32_FLOAT',
    'D24_UNORM_S8_UINT', 'D32_FLOAT_S8',
}


def classify_format(format_str: str) -> str:
    """分类纹理格式"""
    fmt_upper = format_str.upper()
    
    for depth_fmt in DEPTH_FORMATS:
        if depth_fmt in fmt_upper:
            return "depth"
    
    for comp_fmt in COMPRESSED_FORMATS:
        if comp_fmt in fmt_upper:
            return "compressed"
    
    return "uncompressed"


def is_power_of_two(n: int) -> bool:
    """检查是否是 2 的幂"""
    return n > 0 and (n & (n - 1)) == 0


def estimate_texture_memory(width: int, height: int, depth: int, 
                            mip_levels: int, array_size: int,
                            format_str: str, sample_count: int = 1) -> int:
    """估算纹理内存占用 (bytes)"""
    fmt_upper = format_str.upper()
    
    # 每像素字节数
    if 'BC1' in fmt_upper or 'DXT1' in fmt_upper:
        bpp = 0.5
    elif 'BC' in fmt_upper or 'DXT' in fmt_upper:
        bpp = 1.0
    elif 'ASTC_4X4' in fmt_upper:
        bpp = 1.0
    elif 'ASTC_6X6' in fmt_upper:
        bpp = 0.89
    elif 'ASTC_8X8' in fmt_upper:
        bpp = 0.5
    elif 'R32G32B32A32' in fmt_upper:
        bpp = 16
    elif 'R16G16B16A16' in fmt_upper:
        bpp = 8
    elif 'R32G32' in fmt_upper:
        bpp = 8
    elif 'R8G8B8A8' in fmt_upper or 'B8G8R8A8' in fmt_upper:
        bpp = 4
    elif 'R10G10B10A2' in fmt_upper:
        bpp = 4
    elif 'R16G16' in fmt_upper:
        bpp = 4
    elif 'R32' in fmt_upper or 'D32' in fmt_upper:
        bpp = 4
    elif 'R16' in fmt_upper or 'D16' in fmt_upper:
        bpp = 2
    elif 'R8G8' in fmt_upper:
        bpp = 2
    elif 'R8' in fmt_upper:
        bpp = 1
    elif 'D24' in fmt_upper:
        bpp = 4
    else:
        bpp = 4  # 默认
    
    base_size = int(width * height * depth * bpp)
    
    # Mipmap
    if mip_levels > 1:
        base_size = int(base_size * 1.33)
    
    total = base_size * array_size * sample_count
    return total


# =============================================================================
# 分析器核心类
# =============================================================================

class RDCAnalyzer:
    """RDC 文件分析器"""
    
    def __init__(self, platform: str = "pc"):
        self.platform = platform
        self.thresholds = THRESHOLDS_PC if platform == "pc" else THRESHOLDS_MOBILE
        self.result = AnalysisResult()
        
        # 状态跟踪
        self._last_state = {}
        self._state_change_counts = defaultdict(int)
        self._redundant_counts = defaultdict(int)
        self._shader_bind_counts = defaultdict(int)
        self._texture_bind_counts = defaultdict(int)
        self._buffer_bind_counts = defaultdict(int)
        
        # Pass 识别状态
        self._current_marker_stack = []
        self._rt_usage = defaultdict(int)
        self._rt_clear_counts = defaultdict(int)
    
    def analyze_file(self, filepath: str) -> AnalysisResult:
        """分析 RDC 文件"""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"文件不存在: {filepath}")
        
        self.result.meta = {
            'file_name': os.path.basename(filepath),
            'file_size': os.path.getsize(filepath),
            'analysis_time': datetime.now().isoformat(),
            'platform': self.platform,
            'analyzer_version': '2.0',
        }
        
        if HAS_RENDERDOC:
            return self._analyze_with_api(filepath)
        else:
            return self._analyze_binary(filepath)
    
    def _analyze_with_api(self, filepath: str) -> AnalysisResult:
        """使用 RenderDoc API 分析"""
        cap = rd.OpenCaptureFile()
        result = cap.OpenFile(filepath, "", None)
        
        if result != rd.ResultCode.Succeeded:
            raise RuntimeError(f"无法打开 RDC 文件: {result}")
        
        try:
            self.result.meta['api'] = cap.DriverName()
            
            # 解析回放选项
            opts = rd.ReplayOptions()
            status, controller = cap.OpenCapture(opts, None)
            
            if status != rd.ResultCode.Succeeded:
                raise RuntimeError(f"无法创建回放控制器: {status}")
            
            try:
                # Phase 1: 帧摘要
                self._extract_frame_summary(controller)
                
                # Phase 2: 资源清单
                self._extract_resources(controller)
                
                # Phase 3: Pass 结构 (改进版)
                self._extract_passes_improved(controller)
                
                # Phase 4: 详细状态分析
                self._analyze_states(controller)
                
                # Phase 5: 问题检测
                self._detect_all_issues()
                
            finally:
                controller.Shutdown()
                
        finally:
            cap.Shutdown()
        
        return self.result
    
    def _extract_frame_summary(self, controller):
        """Phase 1: 提取帧摘要"""
        summary = self.result.frame_summary
        actions = controller.GetRootActions()
        
        def traverse_actions(action_list):
            for action in action_list:
                flags = action.flags
                
                if flags & rd.ActionFlags.Drawcall:
                    summary.total_draw_calls += 1
                    
                    num_indices = getattr(action, 'numIndices', 0)
                    num_instances = getattr(action, 'numInstances', 1)
                    
                    summary.total_indices += num_indices * num_instances
                    summary.total_triangles += (num_indices // 3) * num_instances
                    
                    if num_instances > 1:
                        summary.instanced_draws += 1
                    
                    if flags & rd.ActionFlags.Indirect:
                        summary.indirect_draws += 1
                    
                    # 记录 DrawCall
                    dc = DrawCallInfo(
                        event_id=action.eventId,
                        type=self._get_draw_type(flags),
                        index_count=num_indices,
                        instance_count=num_instances,
                    )
                    self.result.draw_calls.append(dc)
                    
                    # 小 Draw 检测
                    if num_indices < self.thresholds['small_draw_vertices']:
                        summary.small_draw_count += 1
                    
                elif flags & rd.ActionFlags.Dispatch:
                    summary.total_dispatches += 1
                
                if action.children:
                    traverse_actions(action.children)
        
        traverse_actions(actions)
        
        # 计算效率指标
        if summary.total_draw_calls > 0:
            summary.avg_vertices_per_draw = summary.total_indices / summary.total_draw_calls
            summary.small_draw_ratio = summary.small_draw_count / summary.total_draw_calls
    
    def _get_draw_type(self, flags) -> str:
        """获取 Draw 类型名称"""
        if flags & rd.ActionFlags.Indexed:
            if flags & rd.ActionFlags.Instanced:
                return "DrawIndexedInstanced"
            return "DrawIndexed"
        else:
            if flags & rd.ActionFlags.Instanced:
                return "DrawInstanced"
            return "Draw"
    
    def _extract_resources(self, controller):
        """Phase 2: 提取资源清单"""
        summary = self.result.frame_summary
        
        # 纹理
        textures = controller.GetTextures()
        for tex in textures:
            tex_info = TextureInfo(
                id=f"0x{tex.resourceId.id():08X}",
                name=tex.name if hasattr(tex, 'name') else "",
                width=tex.width,
                height=tex.height,
                depth=getattr(tex, 'depth', 1),
                array_size=getattr(tex, 'arraysize', 1),
                mip_levels=getattr(tex, 'mips', 1),
                sample_count=getattr(tex, 'msSamp', 1),
            )
            
            # 格式
            if hasattr(tex.format, 'Name'):
                tex_info.format = tex.format.Name()
            else:
                tex_info.format = str(tex.format)
            
            tex_info.format_category = classify_format(tex_info.format)
            tex_info.memory_bytes = estimate_texture_memory(
                tex_info.width, tex_info.height, tex_info.depth,
                tex_info.mip_levels, tex_info.array_size,
                tex_info.format, tex_info.sample_count
            )
            
            # 检测纹理问题
            self._check_texture_issues(tex_info)
            
            self.result.textures.append(tex_info)
            summary.texture_count += 1
            summary.estimated_texture_memory_mb += tex_info.memory_bytes / (1024 * 1024)
            
            # RT/DS 统计
            if tex_info.format_category == "depth":
                summary.depth_stencil_count += 1
        
        # 缓冲区
        buffers = controller.GetBuffers()
        for buf in buffers:
            buf_info = BufferInfo(
                id=f"0x{buf.resourceId.id():08X}",
                name=getattr(buf, 'name', ""),
                size_bytes=buf.length,
            )
            
            # 检测 Buffer 问题
            if buf_info.size_bytes > self.thresholds['dynamic_buffer_size_warning']:
                buf_info.issues.append("LARGE_BUFFER")
            
            self.result.buffers.append(buf_info)
            summary.buffer_count += 1
            summary.estimated_buffer_memory_mb += buf_info.size_bytes / (1024 * 1024)
        
        summary.estimated_total_memory_mb = (
            summary.estimated_texture_memory_mb + 
            summary.estimated_buffer_memory_mb
        )
    
    def _extract_passes_improved(self, controller):
        """Phase 3: 改进的 Pass 结构识别"""
        actions = controller.GetRootActions()
        
        current_pass = None
        pass_index = 0
        last_rt_signature = None
        last_ds_id = None
        
        def get_rt_signature(state) -> Tuple:
            """获取 RT 签名 (所有 RT + DS 的组合)"""
            rt_ids = []
            ds_id = None
            
            try:
                # 获取所有 RT
                if hasattr(state, 'GetOutputTargets'):
                    targets = state.GetOutputTargets()
                    for t in targets:
                        if t.resourceId.id() != 0:
                            rt_ids.append(t.resourceId.id())
                
                # 获取 DS
                if hasattr(state, 'GetDepthTarget'):
                    ds = state.GetDepthTarget()
                    if ds.resourceId.id() != 0:
                        ds_id = ds.resourceId.id()
            except:
                pass
            
            return (tuple(rt_ids), ds_id)
        
        def process_action(action, depth=0):
            nonlocal current_pass, pass_index, last_rt_signature, last_ds_id
            
            flags = action.flags
            
            # 处理 Marker
            if flags & rd.ActionFlags.PushMarker:
                self._current_marker_stack.append(action.customName if hasattr(action, 'customName') else "")
            elif flags & rd.ActionFlags.PopMarker:
                if self._current_marker_stack:
                    self._current_marker_stack.pop()
            
            # 处理 Clear
            is_clear = flags & rd.ActionFlags.Clear
            
            # 处理 Draw/Dispatch
            is_draw = flags & rd.ActionFlags.Drawcall
            is_dispatch = flags & rd.ActionFlags.Dispatch
            
            if is_draw or is_dispatch or is_clear:
                controller.SetFrameEvent(action.eventId, False)
                state = controller.GetPipelineState()
                current_signature = get_rt_signature(state)
                
                # 检测 Pass 边界: RT 变化 或 Clear 操作
                need_new_pass = False
                
                if current_signature != last_rt_signature:
                    need_new_pass = True
                elif is_clear and current_pass and current_pass.draw_count > 0:
                    # Clear 在已有 Draw 的 Pass 中，可能是新 Pass 开始
                    need_new_pass = True
                
                if need_new_pass:
                    if current_pass is not None:
                        current_pass.end_event_id = action.eventId - 1
                        self.result.render_passes.append(current_pass)
                    
                    pass_index += 1
                    marker_name = " > ".join(self._current_marker_stack) if self._current_marker_stack else ""
                    
                    current_pass = RenderPassInfo(
                        index=pass_index,
                        name=marker_name if marker_name else f"Pass {pass_index}",
                        start_event_id=action.eventId,
                        marker_name=marker_name,
                    )
                    
                    # 记录 RT 信息
                    rt_ids, ds_id = current_signature
                    for rt_id in rt_ids:
                        current_pass.render_targets.append({
                            'texture_id': f"0x{rt_id:08X}",
                        })
                        self._rt_usage[rt_id] += 1
                    
                    if ds_id:
                        current_pass.depth_stencil = {
                            'texture_id': f"0x{ds_id:08X}",
                        }
                    
                    last_rt_signature = current_signature
                
                # 更新 Pass 统计
                if current_pass:
                    if is_draw:
                        current_pass.draw_count += 1
                        current_pass.total_vertices += getattr(action, 'numIndices', 0)
                    elif is_dispatch:
                        current_pass.dispatch_count += 1
                    elif is_clear:
                        current_pass.clear_count += 1
                        # 记录 Clear 次数
                        rt_ids, ds_id = current_signature
                        for rt_id in rt_ids:
                            self._rt_clear_counts[rt_id] += 1
            
            # 递归子 Action
            if action.children:
                for child in action.children:
                    process_action(child, depth + 1)
        
        for action in actions:
            process_action(action)
        
        if current_pass is not None:
            self.result.render_passes.append(current_pass)
        
        self.result.frame_summary.render_target_changes = len(self.result.render_passes)
        
        # 检测全屏 Pass
        self._detect_fullscreen_passes()
    
    def _detect_fullscreen_passes(self):
        """检测全屏后处理 Pass"""
        fullscreen_count = 0
        for p in self.result.render_passes:
            # 全屏 Pass 通常: 1-2 个 Draw，顶点数 3-6
            if p.draw_count <= 2 and p.total_vertices <= 6:
                p.is_fullscreen = True
                fullscreen_count += 1
        
        if fullscreen_count > self.thresholds['fullscreen_pass_warning']:
            self.result.issues.append(Issue(
                severity="info",
                category="performance",
                code=RuleID.OD_003,
                message=f"全屏后处理 Pass 过多: {fullscreen_count}",
                threshold=self.thresholds['fullscreen_pass_warning'],
                actual=fullscreen_count,
                suggestion="考虑合并后处理 Pass 或使用 Compute Shader"
            ))
    
    def _analyze_states(self, controller):
        """Phase 4: 详细状态分析"""
        actions = controller.GetRootActions()
        
        last_vs = None
        last_ps = None
        last_blend_enabled = None
        last_depth_write = None
        last_cull_mode = None
        
        transparent_draws = 0
        state_switches = 0
        
        def analyze_action(action):
            nonlocal last_vs, last_ps, last_blend_enabled, last_depth_write, last_cull_mode
            nonlocal transparent_draws, state_switches
            
            if action.flags & rd.ActionFlags.Drawcall:
                controller.SetFrameEvent(action.eventId, False)
                state = controller.GetPipelineState()
                
                # 获取 Shader
                try:
                    pipe = state.GetGraphicsPipelineObject()
                    vs_id = str(state.GetShader(rd.ShaderStage.Vertex))
                    ps_id = str(state.GetShader(rd.ShaderStage.Pixel))
                    
                    if vs_id != last_vs or ps_id != last_ps:
                        state_switches += 1
                        self.result.frame_summary.shader_changes += 1
                    
                    last_vs = vs_id
                    last_ps = ps_id
                except:
                    pass
                
                # 获取混合状态
                try:
                    om = state.GetOutputMerger()
                    if hasattr(om, 'blendState'):
                        blend = om.blendState
                        if hasattr(blend, 'blends') and len(blend.blends) > 0:
                            blend_enabled = blend.blends[0].enabled
                            if blend_enabled:
                                transparent_draws += 1
                            
                            if blend_enabled != last_blend_enabled:
                                self.result.frame_summary.blend_state_changes += 1
                            last_blend_enabled = blend_enabled
                except:
                    pass
                
                # 获取深度状态
                try:
                    ds = state.GetDepthState()
                    if hasattr(ds, 'depthEnable'):
                        depth_write = ds.depthWriteEnable if hasattr(ds, 'depthWriteEnable') else True
                        if depth_write != last_depth_write:
                            self.result.frame_summary.depth_state_changes += 1
                        last_depth_write = depth_write
                        
                        # 检测 RD_STATE_001: Depth Write + Blend
                        if depth_write and last_blend_enabled:
                            # 找到对应的 DrawCall 并标记
                            for dc in self.result.draw_calls:
                                if dc.event_id == action.eventId:
                                    dc.depth_write = True
                                    dc.blend_enabled = True
                except:
                    pass
            
            if action.children:
                for child in action.children:
                    analyze_action(child)
        
        for action in actions:
            analyze_action(action)
        
        # 更新透明物体统计
        summary = self.result.frame_summary
        if summary.total_draw_calls > 0:
            summary.transparent_draw_count = transparent_draws
            summary.transparent_draw_ratio = transparent_draws / summary.total_draw_calls
        
        # 计算状态切换率
        if summary.total_draw_calls > 1:
            summary.redundant_state_ratio = 1.0 - (state_switches / summary.total_draw_calls)
    
    def _check_texture_issues(self, tex: TextureInfo):
        """检查纹理相关问题"""
        thresholds = self.thresholds
        
        # RD_TEX_001: 大纹理未压缩
        if (tex.format_category == "uncompressed" and 
            tex.width >= thresholds['texture_uncompressed_size'] and
            tex.height >= thresholds['texture_uncompressed_size']):
            tex.issues.append("LARGE_UNCOMPRESSED")
        
        # RD_TEX_002: 非 2 的幂
        if not (is_power_of_two(tex.width) and is_power_of_two(tex.height)):
            tex.issues.append("NON_POWER_OF_TWO")
        
        # RD_TEX_003: 缺少 Mipmap
        if (tex.mip_levels == 1 and 
            tex.width > thresholds['texture_no_mipmap_size'] and 
            tex.height > thresholds['texture_no_mipmap_size'] and
            tex.format_category != "depth"):
            tex.issues.append("NO_MIPMAP")
        
        # RD_TEX_004: 超大纹理
        if (tex.width >= thresholds['texture_huge_size'] or 
            tex.height >= thresholds['texture_huge_size']):
            tex.issues.append("HUGE_TEXTURE")
    
    def _detect_all_issues(self):
        """综合问题检测"""
        summary = self.result.frame_summary
        thresholds = self.thresholds
        
        # === Draw Call 规则 ===
        
        # RD_DC_001: Draw Call 数量
        if summary.total_draw_calls > thresholds['draw_call_error']:
            self.result.issues.append(Issue(
                severity="error",
                category="performance",
                code=RuleID.DC_001,
                message=f"Draw Call 数量 ({summary.total_draw_calls}) 严重超标",
                threshold=thresholds['draw_call_error'],
                actual=summary.total_draw_calls,
                suggestion="使用 GPU Instancing、合批或 LOD 优化",
                location_path="Frame Summary > Draw Calls"
            ))
        elif summary.total_draw_calls > thresholds['draw_call_warning']:
            self.result.issues.append(Issue(
                severity="warning",
                category="performance",
                code=RuleID.DC_001,
                message=f"Draw Call 数量 ({summary.total_draw_calls}) 较高",
                threshold=thresholds['draw_call_warning'],
                actual=summary.total_draw_calls,
                suggestion="考虑合批优化"
            ))
        
        # RD_DC_005: 空 Draw Call
        empty_draws = [dc for dc in self.result.draw_calls if dc.index_count == 0]
        if empty_draws:
            self.result.issues.append(Issue(
                severity="warning",
                category="correctness",
                code=RuleID.DC_005,
                message=f"存在 {len(empty_draws)} 个空 Draw Call (顶点数=0)",
                actual=len(empty_draws),
                suggestion="检查渲染逻辑，移除无效绘制",
                event_id=empty_draws[0].event_id if empty_draws else None
            ))
        
        # 小 Draw 占比
        if summary.small_draw_ratio > thresholds['small_draw_ratio_warning']:
            self.result.issues.append(Issue(
                severity="info",
                category="performance",
                code=RuleID.DC_001,  # 子规则
                message=f"{summary.small_draw_count} 个 Draw ({summary.small_draw_ratio*100:.1f}%) < {thresholds['small_draw_vertices']} 顶点",
                threshold=thresholds['small_draw_ratio_warning'],
                actual=summary.small_draw_ratio,
                suggestion="考虑合批或动态合并"
            ))
        
        # === 纹理规则 ===
        
        # RD_TEX_001: 未压缩大纹理汇总
        large_uncompressed = [t for t in self.result.textures if "LARGE_UNCOMPRESSED" in t.issues]
        if large_uncompressed:
            self.result.issues.append(Issue(
                severity="warning",
                category="memory",
                code=RuleID.TEX_001,
                message=f"{len(large_uncompressed)} 个大纹理未使用压缩格式",
                actual=len(large_uncompressed),
                suggestion="使用 BC7/ASTC 压缩格式",
                resource_id=large_uncompressed[0].id,
                location_path=f"Resources > Textures > {large_uncompressed[0].id}"
            ))
        
        # RD_TEX_003: 无 Mipmap 汇总
        no_mipmap = [t for t in self.result.textures if "NO_MIPMAP" in t.issues]
        if no_mipmap:
            self.result.issues.append(Issue(
                severity="warning",
                category="performance",
                code=RuleID.TEX_003,
                message=f"{len(no_mipmap)} 个大纹理缺少 Mipmap",
                actual=len(no_mipmap),
                suggestion="为大纹理生成 Mipmap，减少带宽和走样"
            ))
        
        # RD_TEX_004: 超大纹理汇总
        huge_tex = [t for t in self.result.textures if "HUGE_TEXTURE" in t.issues]
        if huge_tex:
            self.result.issues.append(Issue(
                severity="warning",
                category="memory",
                code=RuleID.TEX_004,
                message=f"{len(huge_tex)} 个超大纹理 (>={thresholds['texture_huge_size']})",
                actual=len(huge_tex),
                suggestion="检查是否必要，考虑使用虚拟纹理或流式加载"
            ))
        
        # RD_TEX_005: 总内存
        if summary.estimated_texture_memory_mb > thresholds['texture_memory_warning_mb']:
            self.result.issues.append(Issue(
                severity="warning",
                category="memory",
                code=RuleID.TEX_005,
                message=f"纹理总内存 {summary.estimated_texture_memory_mb:.0f} MB 较高",
                threshold=thresholds['texture_memory_warning_mb'],
                actual=summary.estimated_texture_memory_mb,
                suggestion="检查冗余纹理，优化纹理尺寸和格式"
            ))
        
        # === 顶点规则 ===
        
        # RD_VERT_001: 总顶点数
        if summary.total_indices > thresholds['vertex_total_warning']:
            self.result.issues.append(Issue(
                severity="warning",
                category="performance",
                code=RuleID.VERT_001,
                message=f"单帧顶点数 {summary.total_indices:,} 较高",
                threshold=thresholds['vertex_total_warning'],
                actual=summary.total_indices,
                suggestion="使用 LOD、遮挡剔除或减少模型复杂度"
            ))
        
        # RD_VERT_002: 单次 Draw 顶点过多
        large_draws = [dc for dc in self.result.draw_calls 
                       if dc.index_count > thresholds['vertex_single_draw_warning']]
        if large_draws:
            self.result.issues.append(Issue(
                severity="info",
                category="performance",
                code=RuleID.VERT_002,
                message=f"{len(large_draws)} 个 Draw 顶点数 > {thresholds['vertex_single_draw_warning']}",
                actual=len(large_draws),
                suggestion="考虑拆分大型 Mesh 或使用 LOD",
                event_id=large_draws[0].event_id
            ))
        
        # === RT 规则 ===
        
        # RD_RT_001: RT 切换频繁
        if summary.render_target_changes > thresholds['rt_switch_warning']:
            self.result.issues.append(Issue(
                severity="info",
                category="performance",
                code=RuleID.RT_001,
                message=f"RT 切换 {summary.render_target_changes} 次",
                threshold=thresholds['rt_switch_warning'],
                actual=summary.render_target_changes,
                suggestion="合并渲染 Pass，减少 RT 切换"
            ))
        
        # RD_RT_004: 多次 Clear
        for rt_id, clear_count in self._rt_clear_counts.items():
            if clear_count > thresholds['rt_clear_per_target_warning']:
                self.result.issues.append(Issue(
                    severity="info",
                    category="performance",
                    code=RuleID.RT_004,
                    message=f"RT 0x{rt_id:08X} 被 Clear {clear_count} 次",
                    threshold=thresholds['rt_clear_per_target_warning'],
                    actual=clear_count,
                    resource_id=f"0x{rt_id:08X}",
                    suggestion="检查是否有冗余 Clear 操作"
                ))
        
        # === Overdraw 规则 ===
        
        # RD_OD_001: 透明物体过多
        if summary.transparent_draw_ratio > thresholds['transparent_ratio_warning']:
            self.result.issues.append(Issue(
                severity="warning",
                category="performance",
                code=RuleID.OD_001,
                message=f"透明物体占比 {summary.transparent_draw_ratio*100:.1f}%",
                threshold=thresholds['transparent_ratio_warning'],
                actual=summary.transparent_draw_ratio,
                suggestion="减少透明物体数量，使用 Alpha Test 替代 Alpha Blend"
            ))
        
        # === Buffer 规则 ===
        
        # RD_BUF_001: Buffer 总内存
        if summary.estimated_buffer_memory_mb > thresholds['buffer_memory_warning_mb']:
            self.result.issues.append(Issue(
                severity="warning",
                category="memory",
                code=RuleID.BUF_001,
                message=f"Buffer 总内存 {summary.estimated_buffer_memory_mb:.0f} MB",
                threshold=thresholds['buffer_memory_warning_mb'],
                actual=summary.estimated_buffer_memory_mb,
                suggestion="检查冗余 Buffer，优化数据布局"
            ))
        
        # 按严重性排序
        severity_order = {"error": 0, "warning": 1, "info": 2}
        self.result.issues.sort(key=lambda x: severity_order.get(x.severity, 3))
    
    def _analyze_binary(self, filepath: str) -> AnalysisResult:
        """
        二进制解析模式 (完整实现)
        
        当 renderdoc 模块不可用时，直接解析 RDC 文件的二进制结构。
        基于 _tmp_analyze_chunks.py 的解析逻辑。
        """
        with open(filepath, 'rb') as f:
            # 读取并验证文件头
            header = self._read_rdc_header(f)
            if header is None:
                raise ValueError("不是有效的 RDC 文件")
            
            self.result.meta['api'] = header.get('driver_name', 'Unknown')
            self.result.meta['parse_mode'] = "binary"
            self.result.meta['rdc_version'] = f"0x{header.get('version', 0):08X}"
            self.result.meta['renderdoc_version'] = header.get('prog_version', '')
            
            file_size = os.path.getsize(filepath)
            
            # 跳转到 Section 开始位置
            f.seek(header['header_length'])
            
            # 读取所有 Sections
            sections = []
            while f.tell() < file_size:
                try:
                    section = self._read_section_header(f)
                    if section is None:
                        break
                    sections.append(section)
                    # 跳到下一个 Section
                    f.seek(section['data_offset'] + section['compressed_len'])
                except Exception as e:
                    break
            
            self.result.meta['section_count'] = len(sections)
            
            # 查找 FrameCapture Section (type=1)
            framecapture = None
            for s in sections:
                if s['type'] == 1:
                    framecapture = s
                    break
            
            if framecapture:
                # 读取并解压 FrameCapture 数据
                f.seek(framecapture['data_offset'])
                compressed_data = f.read(framecapture['compressed_len'])
                
                decompressed = None
                if framecapture['is_lz4_compressed']:
                    if HAS_LZ4:
                        decompressed = self._decompress_lz4_blocks(
                            compressed_data, 
                            framecapture['uncompressed_len']
                        )
                    else:
                        self.result.issues.append(Issue(
                            severity="warning",
                            category="correctness",
                            code="MISSING_LZ4",
                            message="LZ4 模块未安装，无法解压帧数据",
                            suggestion="运行: pip install lz4"
                        ))
                elif not framecapture['is_zstd_compressed']:
                    # 未压缩
                    decompressed = compressed_data
                
                if decompressed:
                    # 解析 Chunks
                    chunks, stats = self._analyze_chunks(
                        decompressed, 
                        header.get('time_freq', 1.0)
                    )
                    
                    # 更新帧摘要
                    summary = self.result.frame_summary
                    summary.total_draw_calls = stats['draw_calls']
                    summary.total_dispatches = stats['dispatches']
                    summary.texture_count = stats.get('texture_creates', 0)
                    summary.buffer_count = stats.get('buffer_creates', 0)
                    summary.shader_count = stats.get('shader_creates', 0)
                    summary.render_target_changes = stats.get('rt_sets', 0)
                    summary.shader_changes = stats.get('shader_sets', 0)
                    
                    self.result.meta['total_chunks'] = stats['total_chunks']
                    self.result.meta['chunk_stats'] = stats.get('by_type', {})
                    
                    # 创建 DrawCall 信息
                    for chunk in chunks:
                        if 'Draw' in chunk.get('name', ''):
                            dc = DrawCallInfo(
                                event_id=chunk.get('index', 0),
                                type=chunk.get('name', 'Unknown'),
                            )
                            self.result.draw_calls.append(dc)
                    
                    # 基于二进制分析的问题检测
                    self._detect_binary_issues(stats)
        
        # 添加二进制模式提示
        self.result.issues.append(Issue(
            severity="info",
            category="correctness",
            code="BINARY_MODE",
            message="使用二进制解析模式，部分高级分析不可用",
            suggestion="在 RenderDoc 环境中运行以获取完整分析（纹理尺寸、格式等）"
        ))
        
        return self.result
    
    def _read_rdc_header(self, f) -> Optional[Dict]:
        """读取 RDC 文件头"""
        # Magic (8 bytes: "RDOC" + 4 padding)
        magic = f.read(8)[:4]
        if magic != b'RDOC':
            return None
        
        # Version (4 bytes)
        version = struct.unpack('<I', f.read(4))[0]
        
        # Header length (4 bytes)
        header_length = struct.unpack('<I', f.read(4))[0]
        
        # Program version (16 bytes, null-terminated string)
        prog_version = f.read(16).rstrip(b'\x00').decode('utf-8', errors='replace')
        
        # Thumbnail
        thumb_width = struct.unpack('<H', f.read(2))[0]
        thumb_height = struct.unpack('<H', f.read(2))[0]
        thumb_length = struct.unpack('<I', f.read(4))[0]
        f.seek(thumb_length, 1)  # 跳过缩略图数据
        
        # CaptureMetaData
        machine_ident = struct.unpack('<Q', f.read(8))[0]
        driver_id = struct.unpack('<I', f.read(4))[0]
        driver_name_len = struct.unpack('<B', f.read(1))[0]
        driver_name = f.read(driver_name_len).rstrip(b'\x00').decode('utf-8', errors='replace')
        
        # CaptureTimeBase (if version >= 0x102)
        time_base = 0
        time_freq = 1.0
        if version >= 0x102:
            time_base = struct.unpack('<Q', f.read(8))[0]
            time_freq = struct.unpack('<d', f.read(8))[0]
        
        return {
            'version': version,
            'header_length': header_length,
            'prog_version': prog_version,
            'driver_id': driver_id,
            'driver_name': driver_name,
            'time_base': time_base,
            'time_freq': time_freq,
        }
    
    def _read_section_header(self, f) -> Optional[Dict]:
        """读取 Section 头部"""
        start_pos = f.tell()
        
        try:
            is_ascii = struct.unpack('<B', f.read(1))[0]
            f.read(3)  # padding
            section_type = struct.unpack('<I', f.read(4))[0]
            compressed_len = struct.unpack('<Q', f.read(8))[0]
            uncompressed_len = struct.unpack('<Q', f.read(8))[0]
            section_version = struct.unpack('<Q', f.read(8))[0]
            section_flags = struct.unpack('<I', f.read(4))[0]
            name_len = struct.unpack('<I', f.read(4))[0]
            
            name = ""
            if 0 < name_len < 1024:
                name = f.read(name_len).rstrip(b'\x00').decode('utf-8', errors='replace')
            
            header_size = 40 + name_len
            data_offset = start_pos + header_size
            
            # Section 压缩标志位
            SECTION_FLAG_LZ4_COMPRESSED = 0x2
            SECTION_FLAG_ZSTD_COMPRESSED = 0x4
            
            return {
                'start': start_pos,
                'type': section_type,
                'name': name,
                'compressed_len': compressed_len,
                'uncompressed_len': uncompressed_len,
                'version': section_version,
                'flags': section_flags,
                'is_lz4_compressed': (section_flags & SECTION_FLAG_LZ4_COMPRESSED) != 0,
                'is_zstd_compressed': (section_flags & SECTION_FLAG_ZSTD_COMPRESSED) != 0,
                'data_offset': data_offset,
                'header_size': header_size,
            }
        except:
            return None
    
    def _decompress_lz4_blocks(self, compressed_data: bytes, uncompressed_size: int) -> Optional[bytes]:
        """
        解压 RenderDoc 自定义的分块 LZ4 格式
        
        RenderDoc 使用流式 LZ4 压缩，格式为:
        - 多个连续的块，每块: [int32_t compSize][压缩数据]
        - 每块解压后最大 1MB (lz4BlockSize = 1024 * 1024)
        """
        if not HAS_LZ4:
            return None
        
        LZ4_BLOCK_SIZE = 1024 * 1024  # 1MB
        
        result = bytearray()
        offset = 0
        total_len = len(compressed_data)
        
        try:
            block_count = 0
            while offset + 4 <= total_len and len(result) < uncompressed_size:
                # 读取压缩块大小 (int32_t)
                comp_size = struct.unpack_from('<i', compressed_data, offset)[0]
                offset += 4
                
                if comp_size <= 0 or comp_size > 2 * LZ4_BLOCK_SIZE:
                    break
                
                if offset + comp_size > total_len:
                    break
                
                # 读取压缩数据
                comp_block = compressed_data[offset:offset + comp_size]
                offset += comp_size
                
                # 解压块
                try:
                    if block_count == 0:
                        decomp_block = lz4.block.decompress(comp_block, uncompressed_size=LZ4_BLOCK_SIZE)
                    else:
                        # 尝试使用前一个块作为字典
                        prev_block = result[-LZ4_BLOCK_SIZE:] if len(result) >= LZ4_BLOCK_SIZE else bytes(result)
                        try:
                            decomp_block = lz4.block.decompress(comp_block, uncompressed_size=LZ4_BLOCK_SIZE, dict=prev_block)
                        except TypeError:
                            decomp_block = lz4.block.decompress(comp_block, uncompressed_size=LZ4_BLOCK_SIZE)
                    
                    result.extend(decomp_block)
                    block_count += 1
                except Exception:
                    break
            
            return bytes(result)
            
        except Exception:
            return None
    
    def _analyze_chunks(self, data: bytes, time_freq: float = 1.0, max_chunks: int = 50000) -> Tuple[List[Dict], Dict]:
        """分析 FrameCapture Section 中的 Chunks"""
        # D3D11 Chunk ID 映射 (基于 d3d11_common.h)
        D3D11_CHUNK_NAMES = {
            0: "Unknown", 1: "DriverInit", 2: "InitialContentsList", 
            3: "InitialContents", 4: "CaptureScope", 5: "CaptureBegin", 6: "CaptureEnd",
            1000: "DeviceInitialisation", 1001: "SetResourceName",
            1002: "CreateSwapBuffer", 1003: "CreateTexture1D", 1004: "CreateTexture2D",
            1005: "CreateTexture3D", 1006: "CreateBuffer",
            1007: "CreateVertexShader", 1008: "CreateHullShader", 1009: "CreateDomainShader",
            1010: "CreateGeometryShader", 1012: "CreatePixelShader", 1013: "CreateComputeShader",
            1017: "CreateShaderResourceView", 1018: "CreateRenderTargetView",
            1019: "CreateDepthStencilView", 1020: "CreateUnorderedAccessView",
            1021: "CreateInputLayout", 1022: "CreateBlendState", 1023: "CreateDepthStencilState",
            1024: "CreateRasterizerState", 1025: "CreateSamplerState",
            1032: "IASetInputLayout", 1033: "IASetVertexBuffers", 1034: "IASetIndexBuffer",
            1035: "IASetPrimitiveTopology",
            1039: "VSSetShader", 1043: "HSSetShader", 1047: "DSSetShader",
            1051: "GSSetShader", 1056: "PSSetShader", 1061: "CSSetShader",
            1065: "OMSetRenderTargets", 1066: "OMSetRenderTargetsAndUnorderedAccessViews",
            1067: "OMSetBlendState", 1068: "OMSetDepthStencilState",
            1069: "DrawIndexedInstanced", 1070: "DrawInstanced", 1071: "DrawIndexed", 1072: "Draw",
            1073: "DrawAuto", 1074: "DrawIndexedInstancedIndirect", 1075: "DrawInstancedIndirect",
            1084: "ClearDepthStencilView", 1085: "ClearRenderTargetView",
            1090: "Dispatch", 1091: "DispatchIndirect",
            1109: "PushMarker", 1110: "SetMarker", 1111: "PopMarker",
            1123: "SwapchainPresent",
        }
        
        # Chunk 头部标志位
        CHUNK_INDEX_MASK = 0x0000FFFF
        CHUNK_CALLSTACK = 0x00010000
        CHUNK_THREAD_ID = 0x00020000
        CHUNK_DURATION = 0x00040000
        CHUNK_TIMESTAMP = 0x00080000
        CHUNK_64BIT_SIZE = 0x00100000
        CHUNK_ALIGNMENT = 64
        
        def align_to(offset: int, alignment: int) -> int:
            return ((offset + alignment - 1) // alignment) * alignment
        
        def parse_chunk_header(offset: int) -> Tuple[Optional[Dict], int]:
            if offset + 4 > len(data):
                return None, offset
            
            control = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            
            chunk_id = control & CHUNK_INDEX_MASK
            
            # 跳过 Callstack
            if control & CHUNK_CALLSTACK:
                if offset + 4 > len(data):
                    return None, offset
                num_frames = struct.unpack_from('<I', data, offset)[0]
                offset += 4
                if 0 < num_frames < 4096:
                    offset += num_frames * 8
            
            # 跳过 Thread ID
            if control & CHUNK_THREAD_ID:
                offset += 8
            
            # 跳过 Duration
            if control & CHUNK_DURATION:
                offset += 8
            
            # 跳过 Timestamp
            if control & CHUNK_TIMESTAMP:
                offset += 8
            
            # 读取 Length
            if control & CHUNK_64BIT_SIZE:
                if offset + 8 > len(data):
                    return None, offset
                length = struct.unpack_from('<Q', data, offset)[0]
                offset += 8
            else:
                if offset + 4 > len(data):
                    return None, offset
                length = struct.unpack_from('<I', data, offset)[0]
                offset += 4
            
            return {
                'chunk_id': chunk_id,
                'control': control,
                'length': length,
                'data_offset': offset,
            }, offset
        
        chunks = []
        stats = {
            'total_chunks': 0,
            'draw_calls': 0,
            'dispatches': 0,
            'resource_creates': 0,
            'texture_creates': 0,
            'buffer_creates': 0,
            'shader_creates': 0,
            'rt_sets': 0,
            'shader_sets': 0,
            'state_sets': 0,
            'by_type': {},
        }
        
        offset = 0
        chunk_index = 0
        
        while offset < len(data) and chunk_index < max_chunks:
            chunk, new_offset = parse_chunk_header(offset)
            
            if chunk is None:
                break
            
            chunk_id = chunk['chunk_id']
            chunk_name = D3D11_CHUNK_NAMES.get(chunk_id, f"Unknown({chunk_id})")
            chunk['name'] = chunk_name
            chunk['index'] = chunk_index
            
            # 更新统计
            stats['total_chunks'] += 1
            stats['by_type'][chunk_name] = stats['by_type'].get(chunk_name, 0) + 1
            
            # 分类统计
            if 'Draw' in chunk_name:
                stats['draw_calls'] += 1
            elif 'Dispatch' in chunk_name:
                stats['dispatches'] += 1
            elif 'CreateTexture' in chunk_name or 'CreateRenderTargetView' in chunk_name:
                stats['resource_creates'] += 1
                stats['texture_creates'] += 1
            elif 'CreateBuffer' in chunk_name:
                stats['resource_creates'] += 1
                stats['buffer_creates'] += 1
            elif 'CreateVertexShader' in chunk_name or 'CreatePixelShader' in chunk_name or \
                 'CreateComputeShader' in chunk_name or 'CreateHullShader' in chunk_name or \
                 'CreateDomainShader' in chunk_name or 'CreateGeometryShader' in chunk_name:
                stats['resource_creates'] += 1
                stats['shader_creates'] += 1
            elif 'SetShader' in chunk_name:
                stats['shader_sets'] += 1
            elif 'OMSetRenderTargets' in chunk_name:
                stats['rt_sets'] += 1
            elif 'Set' in chunk_name:
                stats['state_sets'] += 1
            
            chunks.append(chunk)
            
            # 跳过 chunk 数据，然后对齐到 64 字节边界
            raw_next = new_offset + chunk['length']
            offset = align_to(raw_next, CHUNK_ALIGNMENT)
            chunk_index += 1
        
        return chunks, stats
    
    def _detect_binary_issues(self, stats: Dict):
        """基于二进制分析的问题检测"""
        thresholds = self.thresholds
        
        # Draw Call 数量
        if stats['draw_calls'] > thresholds['draw_call_error']:
            self.result.issues.append(Issue(
                severity="error",
                category="performance",
                code=RuleID.DC_001,
                message=f"Draw Call 数量 ({stats['draw_calls']}) 严重超标",
                threshold=thresholds['draw_call_error'],
                actual=stats['draw_calls'],
                suggestion="使用 GPU Instancing、合批或 LOD 优化"
            ))
        elif stats['draw_calls'] > thresholds['draw_call_warning']:
            self.result.issues.append(Issue(
                severity="warning",
                category="performance",
                code=RuleID.DC_001,
                message=f"Draw Call 数量 ({stats['draw_calls']}) 较高",
                threshold=thresholds['draw_call_warning'],
                actual=stats['draw_calls'],
                suggestion="考虑合批优化"
            ))
        
        # RT 切换频繁
        if stats['rt_sets'] > thresholds['rt_switch_warning']:
            self.result.issues.append(Issue(
                severity="info",
                category="performance",
                code=RuleID.RT_001,
                message=f"RT 设置 {stats['rt_sets']} 次，可能存在频繁切换",
                threshold=thresholds['rt_switch_warning'],
                actual=stats['rt_sets'],
                suggestion="合并渲染 Pass，减少 RT 切换"
            ))
        
        # Shader 切换
        if stats['shader_sets'] > stats['draw_calls'] * 0.8:
            self.result.issues.append(Issue(
                severity="info",
                category="performance",
                code=RuleID.SHADER_001,
                message=f"Shader 设置次数 ({stats['shader_sets']}) 接近 Draw Call 数",
                actual=stats['shader_sets'],
                suggestion="按材质排序减少 Shader 切换"
            ))
    
    def to_json(self) -> str:
        """导出为 JSON"""
        def convert(obj):
            if hasattr(obj, '__dataclass_fields__'):
                return asdict(obj)
            return str(obj)
        
        return json.dumps(asdict(self.result), indent=2, default=convert, ensure_ascii=False)
    
    def to_markdown(self) -> str:
        """导出为 Markdown 报告"""
        r = self.result
        s = r.frame_summary
        
        lines = [
            "# RDC 分析报告 v2.0",
            "",
            f"**文件**: `{r.meta.get('file_name', 'Unknown')}`",
            f"**分析时间**: {r.meta.get('analysis_time', '')}",
            f"**平台配置**: {r.meta.get('platform', 'pc').upper()}",
            f"**图形 API**: {r.meta.get('api', 'Unknown')}",
            "",
            "---",
            "",
            "## 📊 帧摘要",
            "",
            "### 绘制统计",
            "",
            "| 指标 | 值 | 状态 |",
            "|------|------|------|",
            f"| Draw Calls | {s.total_draw_calls:,} | {self._status_icon(s.total_draw_calls, self.thresholds['draw_call_warning'], self.thresholds['draw_call_error'])} |",
            f"| Compute Dispatches | {s.total_dispatches:,} | - |",
            f"| 三角形数 | {s.total_triangles:,} | - |",
            f"| 顶点数 | {s.total_indices:,} | {self._status_icon(s.total_indices, self.thresholds['vertex_total_warning'])} |",
            f"| Instanced Draws | {s.instanced_draws:,} | - |",
            f"| 透明物体占比 | {s.transparent_draw_ratio*100:.1f}% | {self._status_icon(s.transparent_draw_ratio, self.thresholds['transparent_ratio_warning'])} |",
            "",
            "### 资源统计",
            "",
            "| 指标 | 值 |",
            "|------|------|",
            f"| 纹理数量 | {s.texture_count:,} |",
            f"| Buffer 数量 | {s.buffer_count:,} |",
            f"| 纹理内存 | {s.estimated_texture_memory_mb:.1f} MB |",
            f"| Buffer 内存 | {s.estimated_buffer_memory_mb:.1f} MB |",
            f"| **总显存** | **{s.estimated_total_memory_mb:.1f} MB** |",
            "",
            "### 状态切换",
            "",
            "| 指标 | 次数 |",
            "|------|------|",
            f"| RT 切换 | {s.render_target_changes} |",
            f"| Shader 切换 | {s.shader_changes} |",
            f"| Blend 状态切换 | {s.blend_state_changes} |",
            f"| Depth 状态切换 | {s.depth_state_changes} |",
            "",
        ]
        
        # 问题列表
        if r.issues:
            error_count = len([i for i in r.issues if i.severity == "error"])
            warn_count = len([i for i in r.issues if i.severity == "warning"])
            info_count = len([i for i in r.issues if i.severity == "info"])
            
            lines.extend([
                "---",
                "",
                f"## ⚠️ 检测到的问题 ({error_count} 错误, {warn_count} 警告, {info_count} 建议)",
                "",
            ])
            
            for issue in r.issues:
                icon = {"error": "🔴", "warning": "🟠", "info": "🟡"}.get(issue.severity, "⚪")
                lines.append(f"### {icon} [{issue.code}] {issue.message}")
                lines.append("")
                
                if issue.threshold is not None and issue.actual is not None:
                    lines.append(f"- **阈值**: {issue.threshold} | **实际**: {issue.actual}")
                
                if issue.resource_id:
                    lines.append(f"- **关联资源**: `{issue.resource_id}`")
                
                if issue.event_id:
                    lines.append(f"- **事件 ID**: {issue.event_id}")
                
                if issue.location_path:
                    lines.append(f"- **定位**: {issue.location_path}")
                
                if issue.suggestion:
                    lines.append(f"- **建议**: {issue.suggestion}")
                
                lines.append("")
        
        # Pass 结构
        if r.render_passes:
            lines.extend([
                "---",
                "",
                f"## 🎬 渲染 Pass 结构 ({len(r.render_passes)} 个)",
                "",
                "| # | 名称 | 事件范围 | Draw | Dispatch | Clear | 全屏 |",
                "|---|------|----------|------|----------|-------|------|",
            ])
            
            for p in r.render_passes[:30]:
                name = p.marker_name if p.marker_name else p.name
                name = name[:30] + "..." if len(name) > 30 else name
                fullscreen = "✓" if p.is_fullscreen else ""
                lines.append(f"| {p.index} | {name} | {p.start_event_id}-{p.end_event_id} | {p.draw_count} | {p.dispatch_count} | {p.clear_count} | {fullscreen} |")
            
            if len(r.render_passes) > 30:
                lines.append(f"| ... | ({len(r.render_passes) - 30} more) | | | | | |")
            
            lines.append("")
        
        # Top 纹理
        if r.textures:
            lines.extend([
                "---",
                "",
                "## 📦 纹理资源 (Top 10 by Memory)",
                "",
                "| ID | 尺寸 | 格式 | 内存 | 问题 |",
                "|----|------|------|------|------|",
            ])
            
            sorted_tex = sorted(r.textures, key=lambda t: -t.memory_bytes)[:10]
            for t in sorted_tex:
                size_str = f"{t.width}x{t.height}"
                if t.depth > 1:
                    size_str += f"x{t.depth}"
                if t.array_size > 1:
                    size_str += f" [{t.array_size}]"
                
                mem_mb = t.memory_bytes / (1024 * 1024)
                fmt_short = t.format[:25] + "..." if len(t.format) > 25 else t.format
                issues_str = ", ".join(t.issues[:2]) if t.issues else "✓"
                
                lines.append(f"| `{t.id}` | {size_str} | {fmt_short} | {mem_mb:.1f} MB | {issues_str} |")
            
            lines.append("")
        
        # 生成 LLM Prompt
        lines.extend([
            "---",
            "",
            "## 🤖 LLM 分析提示",
            "",
            "```",
            f"分析 RDC 文件: {r.meta.get('file_name', '')}",
            f"平台: {r.meta.get('platform', 'pc').upper()}",
            "",
            f"帧统计: {s.total_draw_calls} Draw Calls, {s.total_triangles:,} 三角形, {s.estimated_total_memory_mb:.0f} MB 显存",
            "",
            f"检测到 {len(r.issues)} 个问题:",
        ])
        
        for i, issue in enumerate(r.issues[:5], 1):
            lines.append(f"  {i}. [{issue.severity.upper()}] {issue.code}: {issue.message}")
        
        if len(r.issues) > 5:
            lines.append(f"  ... 及其他 {len(r.issues) - 5} 个问题")
        
        lines.extend([
            "",
            "请基于以上数据给出性能优化建议。",
            "```",
            "",
        ])
        
        return "\n".join(lines)
    
    def _status_icon(self, value, warning_threshold, error_threshold=None) -> str:
        """根据阈值返回状态图标"""
        if error_threshold and value > error_threshold:
            return "🔴"
        elif value > warning_threshold:
            return "🟠"
        else:
            return "✅"


# =============================================================================
# 命令行入口
# =============================================================================

def analyze_rdc(filepath: str, platform: str = "pc", 
                output_json: str = None, output_md: str = None) -> AnalysisResult:
    """
    分析 RDC 文件
    
    Args:
        filepath: RDC 文件路径
        platform: "pc" 或 "mobile"
        output_json: JSON 输出路径
        output_md: Markdown 输出路径
    
    Returns:
        AnalysisResult
    """
    analyzer = RDCAnalyzer(platform=platform)
    result = analyzer.analyze_file(filepath)
    
    if output_json:
        with open(output_json, 'w', encoding='utf-8') as f:
            f.write(analyzer.to_json())
        print(f"[+] JSON 报告: {output_json}")
    
    if output_md:
        with open(output_md, 'w', encoding='utf-8') as f:
            f.write(analyzer.to_markdown())
        print(f"[+] Markdown 报告: {output_md}")
    
    return result


def main():
    """命令行入口"""
    if len(sys.argv) < 2:
        print("RDC 分析器 v2.0")
        print("")
        print("用法: python rdc_analyzer.py <rdc_file> [选项]")
        print("")
        print("选项:")
        print("  --platform pc|mobile  平台配置 (默认: pc)")
        print("  --json <file>         输出 JSON 报告")
        print("  --md <file>           输出 Markdown 报告")
        print("")
        print("示例:")
        print("  python rdc_analyzer.py capture.rdc")
        print("  python rdc_analyzer.py capture.rdc --platform mobile")
        print("  python rdc_analyzer.py capture.rdc --json report.json --md report.md")
        return 1
    
    filepath = sys.argv[1]
    platform = "pc"
    output_json = None
    output_md = None
    
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--platform" and i + 1 < len(sys.argv):
            platform = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--json" and i + 1 < len(sys.argv):
            output_json = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--md" and i + 1 < len(sys.argv):
            output_md = sys.argv[i + 1]
            i += 2
        else:
            i += 1
    
    if not output_json and not output_md:
        base_name = os.path.splitext(filepath)[0]
        output_json = f"{base_name}_analysis.json"
        output_md = f"{base_name}_analysis.md"
    
    print(f"[*] 分析文件: {filepath}")
    print(f"[*] 平台: {platform.upper()}")
    print("")
    
    try:
        result = analyze_rdc(filepath, platform, output_json, output_md)
        
        s = result.frame_summary
        print("")
        print("=" * 50)
        print("[+] 分析完成")
        print("=" * 50)
        print(f"  Draw Calls:    {s.total_draw_calls:>8,}")
        print(f"  三角形:        {s.total_triangles:>8,}")
        print(f"  纹理:          {s.texture_count:>8} ({s.estimated_texture_memory_mb:.1f} MB)")
        print(f"  Buffer:        {s.buffer_count:>8} ({s.estimated_buffer_memory_mb:.1f} MB)")
        print(f"  检测问题:      {len(result.issues):>8}")
        print("")
        
        # 显示重要问题
        for issue in result.issues[:5]:
            icon = {"error": "[!]", "warning": "[?]", "info": "[i]"}.get(issue.severity, "[ ]")
            print(f"  {icon} [{issue.code}] {issue.message}")
        
        if len(result.issues) > 5:
            print(f"  ... 及其他 {len(result.issues) - 5} 个问题")
        
    except Exception as e:
        print(f"[X] 分析失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
