#!/usr/bin/env python3
"""
Contract Field Schemas - 详细的字段结构定义 v2.2

本模块定义了 ReportDataContract 各字段的详细结构，
供解析器和渲染器参考。

Changes v2.2:
    - 新增 ShaderSchema: 完整 Shader 字段定义
    - 新增 PipelineStateSchema: Pipeline State 字段定义
    - 新增 EventSchema: 扩展事件字段
    - 新增 TextureSchema: 扩展纹理字段
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


# =============================================================================
# Enums
# =============================================================================

class ShaderStage(str, Enum):
    """Shader 阶段类型"""
    VERTEX = "Vertex"
    FRAGMENT = "Fragment"       # Also known as Pixel
    GEOMETRY = "Geometry"
    TESS_CONTROL = "TessControl"   # Also known as Hull
    TESS_EVAL = "TessEval"         # Also known as Domain
    COMPUTE = "Compute"
    MESH = "Mesh"
    AMPLIFICATION = "Amplification"  # Also known as Task
    
    # Vulkan/SPIR-V specific
    RAY_GEN = "RayGen"
    RAY_MISS = "RayMiss"
    RAY_CLOSEST_HIT = "RayClosestHit"
    RAY_ANY_HIT = "RayAnyHit"
    RAY_INTERSECTION = "RayIntersection"


class TextureType(str, Enum):
    """纹理类型"""
    TEXTURE_1D = "Texture1D"
    TEXTURE_2D = "Texture2D"
    TEXTURE_3D = "Texture3D"
    TEXTURE_CUBE = "TextureCube"
    TEXTURE_1D_ARRAY = "Texture1DArray"
    TEXTURE_2D_ARRAY = "Texture2DArray"
    TEXTURE_CUBE_ARRAY = "TextureCubeArray"
    TEXTURE_2D_MS = "Texture2DMS"
    TEXTURE_2D_MS_ARRAY = "Texture2DMSArray"


class FillMode(str, Enum):
    """填充模式"""
    SOLID = "Solid"
    WIREFRAME = "Wireframe"
    POINT = "Point"


class CullMode(str, Enum):
    """剔除模式"""
    NONE = "None"
    FRONT = "Front"
    BACK = "Back"


class CompareFunc(str, Enum):
    """比较函数"""
    NEVER = "Never"
    LESS = "Less"
    EQUAL = "Equal"
    LESS_EQUAL = "LessEqual"
    GREATER = "Greater"
    NOT_EQUAL = "NotEqual"
    GREATER_EQUAL = "GreaterEqual"
    ALWAYS = "Always"


# =============================================================================
# Schema Definitions
# =============================================================================

@dataclass
class ShaderSchema:
    """Shader 数据结构定义
    
    完整的 Shader 信息，包含源码、反射数据等。
    
    Required Fields:
        id: 唯一标识符
        stage: Shader 阶段 (Vertex/Fragment/Compute 等)
        
    Optional Fields:
        resource_id: RenderDoc 资源 ID
        name: Shader 名称
        entry_point: 入口函数名
        source: 源码/反汇编
        source_language: 源码语言 (HLSL/GLSL/SPIR-V)
        compile_flags: 编译标志
        
    Reflection Data:
        input_count: 输入参数数量
        output_count: 输出参数数量
        cbuffer_count: Constant Buffer 数量
        texture_count: 绑定纹理数量
        sampler_count: 采样器数量
        uav_count: UAV 数量
        
    Bindings:
        cbuffers: Constant Buffer 详情列表
        textures: 纹理绑定列表
        samplers: 采样器列表
        uavs: UAV 列表
    """
    
    # Required
    id: int = 0
    stage: str = ""  # ShaderStage value
    
    # Optional
    resource_id: int = 0
    name: str = ""
    entry_point: str = "main"
    source: str = ""
    source_language: str = "Unknown"  # HLSL, GLSL, SPIR-V, DXBC, DXIL
    compile_flags: str = ""
    
    # Reflection counts
    input_count: int = 0
    output_count: int = 0
    cbuffer_count: int = 0
    texture_count: int = 0
    sampler_count: int = 0
    uav_count: int = 0
    
    # Detailed bindings
    cbuffers: List[Dict[str, Any]] = field(default_factory=list)
    textures: List[Dict[str, Any]] = field(default_factory=list)
    samplers: List[Dict[str, Any]] = field(default_factory=list)
    uavs: List[Dict[str, Any]] = field(default_factory=list)
    
    # Input/Output signature
    inputs: List[Dict[str, Any]] = field(default_factory=list)
    outputs: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "resource_id": self.resource_id,
            "name": self.name,
            "stage": self.stage,
            "entry_point": self.entry_point,
            "source": self.source,
            "source_language": self.source_language,
            "compile_flags": self.compile_flags,
            "input_count": self.input_count,
            "output_count": self.output_count,
            "cbuffer_count": self.cbuffer_count,
            "texture_count": self.texture_count,
            "sampler_count": self.sampler_count,
            "uav_count": self.uav_count,
            "cbuffers": self.cbuffers,
            "textures": self.textures,
            "samplers": self.samplers,
            "uavs": self.uavs,
            "inputs": self.inputs,
            "outputs": self.outputs,
        }


@dataclass
class PipelineStateSchema:
    """Pipeline State 数据结构定义
    
    特定事件点的完整管线状态快照。
    
    Context:
        event_id: 关联的事件 ID
        
    Shaders:
        vertex_shader: Vertex Shader ID
        fragment_shader: Fragment/Pixel Shader ID
        geometry_shader: Geometry Shader ID (可选)
        hull_shader: Hull/TessControl Shader ID (可选)
        domain_shader: Domain/TessEval Shader ID (可选)
        compute_shader: Compute Shader ID (仅 Compute Pass)
        
    Viewport & Scissor:
        viewport: Viewport 状态
        scissor: Scissor 状态
        
    Rasterizer:
        rasterizer: 光栅化状态
        
    Depth/Stencil:
        depth_stencil: 深度模板状态
        
    Blend:
        blend: 混合状态
        
    Render Targets:
        render_targets: 渲染目标列表
        depth_target: 深度目标
        
    Resources:
        bound_textures: 绑定的纹理列表
        bound_buffers: 绑定的缓冲区列表
        bound_samplers: 绑定的采样器列表
    """
    
    # Context
    event_id: int = 0
    
    # Shader IDs
    vertex_shader: int = 0
    fragment_shader: int = 0
    geometry_shader: int = 0
    hull_shader: int = 0
    domain_shader: int = 0
    compute_shader: int = 0
    
    # Viewport
    viewport: Dict[str, Any] = field(default_factory=lambda: {
        "x": 0.0,
        "y": 0.0,
        "width": 0.0,
        "height": 0.0,
        "min_depth": 0.0,
        "max_depth": 1.0,
    })
    
    # Scissor
    scissor: Dict[str, Any] = field(default_factory=lambda: {
        "x": 0,
        "y": 0,
        "width": 0,
        "height": 0,
        "enabled": False,
    })
    
    # Rasterizer state
    rasterizer: Dict[str, Any] = field(default_factory=lambda: {
        "fill_mode": "Solid",
        "cull_mode": "Back",
        "front_ccw": False,
        "depth_bias": 0,
        "depth_bias_clamp": 0.0,
        "slope_scaled_depth_bias": 0.0,
        "depth_clip": True,
        "scissor_enable": False,
        "multisample": False,
        "antialiased_lines": False,
    })
    
    # Depth/Stencil state
    depth_stencil: Dict[str, Any] = field(default_factory=lambda: {
        "depth_enable": True,
        "depth_write": True,
        "depth_func": "Less",
        "stencil_enable": False,
        "stencil_read_mask": 0xFF,
        "stencil_write_mask": 0xFF,
        "front_face": {
            "fail": "Keep",
            "depth_fail": "Keep",
            "pass": "Keep",
            "func": "Always",
        },
        "back_face": {
            "fail": "Keep",
            "depth_fail": "Keep",
            "pass": "Keep",
            "func": "Always",
        },
    })
    
    # Blend state
    blend: Dict[str, Any] = field(default_factory=lambda: {
        "alpha_to_coverage": False,
        "independent_blend": False,
        "blend_factor": [0.0, 0.0, 0.0, 0.0],
        "sample_mask": 0xFFFFFFFF,
        "targets": [],  # Per-RT blend settings
    })
    
    # Render targets
    render_targets: List[Dict[str, Any]] = field(default_factory=list)
    depth_target: Dict[str, Any] = field(default_factory=dict)
    
    # Bound resources
    bound_textures: List[Dict[str, Any]] = field(default_factory=list)
    bound_buffers: List[Dict[str, Any]] = field(default_factory=list)
    bound_samplers: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "vertex_shader": self.vertex_shader,
            "fragment_shader": self.fragment_shader,
            "geometry_shader": self.geometry_shader,
            "hull_shader": self.hull_shader,
            "domain_shader": self.domain_shader,
            "compute_shader": self.compute_shader,
            "viewport": self.viewport,
            "scissor": self.scissor,
            "rasterizer": self.rasterizer,
            "depth_stencil": self.depth_stencil,
            "blend": self.blend,
            "render_targets": self.render_targets,
            "depth_target": self.depth_target,
            "bound_textures": self.bound_textures,
            "bound_buffers": self.bound_buffers,
            "bound_samplers": self.bound_samplers,
        }


@dataclass
class TextureSchema:
    """纹理数据结构定义 (扩展版)
    
    完整的纹理资源信息。
    
    Required Fields:
        id: 唯一标识符
        width: 宽度 (像素)
        height: 高度 (像素)
        format: 纹理格式
        
    Optional Fields:
        resource_id: RenderDoc 资源 ID
        name: 纹理名称/调试名
        depth: 深度 (3D 纹理)
        array_size: 数组大小
        mip_levels: Mip 层级数
        samples: 多重采样数
        type: 纹理类型
        
    Size Info:
        size_bytes: 估算大小 (字节)
        compressed: 是否压缩格式
        
    Thumbnail:
        thumbnail: Base64 编码的缩略图
        
    Usage Info:
        creation_flags: 创建标志
        usage_events: 使用此纹理的事件列表
        is_render_target: 是否作为渲染目标
        is_depth_buffer: 是否作为深度缓冲
        is_swapchain: 是否是交换链纹理
    """
    
    # Required
    id: int = 0
    width: int = 0
    height: int = 0
    format: str = "Unknown"
    
    # Optional
    resource_id: int = 0
    name: str = ""
    depth: int = 1
    array_size: int = 1
    mip_levels: int = 1
    samples: int = 1
    type: str = "Texture2D"
    
    # Size
    size_bytes: int = 0
    compressed: bool = False
    
    # Thumbnail
    thumbnail: str = ""
    
    # Usage
    creation_flags: int = 0
    usage_events: List[int] = field(default_factory=list)
    is_render_target: bool = False
    is_depth_buffer: bool = False
    is_swapchain: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "resource_id": self.resource_id,
            "name": self.name,
            "width": self.width,
            "height": self.height,
            "depth": self.depth,
            "format": self.format,
            "array_size": self.array_size,
            "mip_levels": self.mip_levels,
            "samples": self.samples,
            "type": self.type,
            "size_bytes": self.size_bytes,
            "compressed": self.compressed,
            "thumbnail": self.thumbnail,
            "creation_flags": self.creation_flags,
            "usage_events": self.usage_events,
            "is_render_target": self.is_render_target,
            "is_depth_buffer": self.is_depth_buffer,
            "is_swapchain": self.is_swapchain,
        }


@dataclass
class EventSchema:
    """事件/Draw Call 数据结构定义 (扩展版)
    
    完整的绘制/调度调用信息。
    
    Required Fields:
        event_id: 事件 ID
        name: 调用名称 (如 "DrawIndexed")
        
    Type Flags:
        is_draw: 是否是绘制调用
        is_dispatch: 是否是计算调度
        is_clear: 是否是清除操作
        is_copy: 是否是复制操作
        is_marker: 是否是调试标记
        
    Draw Info:
        vertex_count: 顶点数
        index_count: 索引数
        instance_count: 实例数
        triangle_count: 三角形数
        base_vertex: 基础顶点偏移
        index_offset: 索引偏移
        vertex_offset: 顶点偏移
        
    Dispatch Info:
        dispatch_x: X 方向线程组数
        dispatch_y: Y 方向线程组数
        dispatch_z: Z 方向线程组数
        
    Context:
        depth: 在调用树中的深度
        debug_marker: 调试标记名称
        parent_event: 父事件 ID
        
    Performance:
        duration_ns: 持续时间 (纳秒)
        gpu_duration_ns: GPU 持续时间 (纳秒)
    """
    
    # Required
    event_id: int = 0
    name: str = ""
    
    # Type flags
    is_draw: bool = False
    is_dispatch: bool = False
    is_clear: bool = False
    is_copy: bool = False
    is_marker: bool = False
    
    # Draw info
    vertex_count: int = 0
    index_count: int = 0
    instance_count: int = 0
    triangle_count: int = 0
    base_vertex: int = 0
    index_offset: int = 0
    vertex_offset: int = 0
    
    # Dispatch info
    dispatch_x: int = 0
    dispatch_y: int = 0
    dispatch_z: int = 0
    
    # Context
    depth: int = 0
    debug_marker: str = ""
    parent_event: int = 0
    
    # Performance
    duration_ns: int = 0
    gpu_duration_ns: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "name": self.name,
            "is_draw": self.is_draw,
            "is_dispatch": self.is_dispatch,
            "is_clear": self.is_clear,
            "is_copy": self.is_copy,
            "is_marker": self.is_marker,
            "vertex_count": self.vertex_count,
            "index_count": self.index_count,
            "instance_count": self.instance_count,
            "triangle_count": self.triangle_count,
            "base_vertex": self.base_vertex,
            "index_offset": self.index_offset,
            "vertex_offset": self.vertex_offset,
            "dispatch_x": self.dispatch_x,
            "dispatch_y": self.dispatch_y,
            "dispatch_z": self.dispatch_z,
            "depth": self.depth,
            "debug_marker": self.debug_marker,
            "parent_event": self.parent_event,
            "duration_ns": self.duration_ns,
            "gpu_duration_ns": self.gpu_duration_ns,
        }


# =============================================================================
# Schema Documentation
# =============================================================================

SCHEMA_DOCS = {
    "shader": {
        "description": "Shader 资源数据",
        "required": ["id", "stage"],
        "optional": ["name", "source", "entry_point", "cbuffer_count", "texture_count"],
    },
    "pipeline_state": {
        "description": "Pipeline State 快照",
        "required": ["event_id"],
        "optional": ["viewport", "scissor", "rasterizer", "depth_stencil", "blend"],
    },
    "texture": {
        "description": "纹理资源数据",
        "required": ["id", "width", "height", "format"],
        "optional": ["name", "depth", "mip_levels", "thumbnail", "size_bytes"],
    },
    "event": {
        "description": "Draw/Dispatch 事件",
        "required": ["event_id", "name"],
        "optional": ["vertex_count", "index_count", "instance_count", "debug_marker"],
    },
}


def get_schema_doc(schema_name: str) -> Dict[str, Any]:
    """获取 Schema 文档"""
    return SCHEMA_DOCS.get(schema_name, {})


def validate_shader_dict(data: Dict[str, Any]) -> bool:
    """验证 Shader 数据是否符合 Schema"""
    required = ["id", "stage"]
    return all(k in data for k in required)


def validate_pipeline_state_dict(data: Dict[str, Any]) -> bool:
    """验证 Pipeline State 数据是否符合 Schema"""
    required = ["event_id"]
    return all(k in data for k in required)


def validate_texture_dict(data: Dict[str, Any]) -> bool:
    """验证 Texture 数据是否符合 Schema"""
    required = ["id", "width", "height", "format"]
    return all(k in data for k in required)


def validate_event_dict(data: Dict[str, Any]) -> bool:
    """验证 Event 数据是否符合 Schema"""
    required = ["event_id", "name"]
    return all(k in data for k in required)
